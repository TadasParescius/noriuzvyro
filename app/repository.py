from app.db import query
from app.errors import ApiError, required

# Only these server-owned identifiers are interpolated into SQL. Client values
# are always supplied separately as psycopg parameters.
TABLES = {'quarry': 'quarries', 'offer': 'offers', 'order': 'orders'}
FIELDS = {
    'quarry': {'name': 'name', 'city': 'city', 'address': 'address', 'phone': 'phone',
               'description': 'description', 'latitude': 'latitude', 'longitude': 'longitude'},
    'offer': {'name': 'name', 'materialType': 'material_type', 'fraction': 'fraction',
              'description': 'description', 'pricePerTonneEur': 'price_per_tonne_eur', 'available': 'available'},
    'order': {'customerName': 'customer_name', 'email': 'email', 'phone': 'phone',
              'deliveryAddress': 'delivery_address', 'quantityTonnes': 'quantity_tonnes',
              'willBeHome': 'will_be_home', 'unloadingInstructions': 'unloading_instructions',
              'paymentMethod': 'payment_method', 'status': 'status'},
}
PARENT = {'offer': 'quarry_id', 'order': 'offer_id'}


def columns(kind):
    fields = {'id': 'id', **FIELDS[kind], 'createdAt': 'created_at', 'updatedAt': 'updated_at'}
    if kind == 'offer':
        fields['quarryId'] = 'quarry_id'
    if kind in ('quarry', 'order'):
        fields['ownerId'] = 'owner_id'
    if kind == 'order':
        fields.update(offerId='offer_id', unitPriceEur='unit_price_eur', materialTotalEur='material_total_eur')
        fields['driverId'] = 'driver_id'
    return ', '.join(f'{column} AS "{name}"' for name, column in fields.items())


def scope(kind, item_id, parent_id=None):
    where, params = 'id=%s', [item_id]
    if kind in PARENT:
        where += f' AND {PARENT[kind]}=%s'
        params.append(parent_id)
    return where, params


def get(kind, item_id, parent_id=None):
    where, params = scope(kind, item_id, parent_id)
    return required(query(f'SELECT {columns(kind)} FROM {TABLES[kind]} WHERE {where}', params))


def list_records(kind, filters, parent_id=None, user=None):
    where, params = [], []
    if kind in PARENT:
        where.append(f'{PARENT[kind]}=%s')
        params.append(parent_id)
    if kind == 'order' and user and user['role'] != 'admin':
        where.append('(owner_id=%s OR driver_id=%s OR offer_id IN (SELECT id FROM offers WHERE quarry_id IN (SELECT id FROM quarries WHERE owner_id=%s)))')
        params.extend([user['id']] * 3)
    for name, value in filters.items():
        expression = {
            'city': 'lower(city)=lower(%s)', 'search': 'strpos(lower(name),lower(%s))>0',
            'materialType': 'material_type=%s', 'available': 'available=%s',
            'minPrice': 'price_per_tonne_eur>=%s', 'maxPrice': 'price_per_tonne_eur<=%s',
            'status': 'status=%s', 'paymentMethod': 'payment_method=%s',
        }.get(name)
        if expression:
            where.append(expression)
            params.append(value)
    sql_filter = ' WHERE ' + ' AND '.join(where) if where else ''
    # One statement provides a consistent count even for an empty page.
    return query(f'''WITH filtered AS (SELECT {columns(kind)} FROM {TABLES[kind]}{sql_filter}),
        paged AS (SELECT * FROM filtered ORDER BY id LIMIT %s OFFSET %s)
        SELECT (SELECT count(*)::int FROM filtered) AS total,
        COALESCE((SELECT json_agg(paged ORDER BY id) FROM paged), '[]'::json) AS data''',
        params + [filters['pageSize'], (filters['page'] - 1) * filters['pageSize']])[0]

def patch(kind, body, item_id, parent_id=None):
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise ApiError(400, 'VALIDATION_ERROR', 'No fields provided for update.')
    values = [data[name] for name in FIELDS[kind] if name in data]
    where, ids = scope(kind, item_id, parent_id)
    assignments = ', '.join(f'{FIELDS[kind][name]}=%s' for name in FIELDS[kind] if name in data)
    return required(query(f'UPDATE {TABLES[kind]} SET {assignments}, updated_at=now() '
                          f'WHERE {where} RETURNING {columns(kind)}', values + ids))


def save(kind, body, parent_id=None, item_id=None, owner_id=None):
    data = body.model_dump()
    names = list(FIELDS[kind].values())
    values = [data[name] for name in FIELDS[kind]]
    if item_id is not None:
        where, ids = scope(kind, item_id, parent_id)
        assignments = ', '.join(f'{name}=%s' for name in names)
        return required(query(f'UPDATE {TABLES[kind]} SET {assignments}, updated_at=now() '
                              f'WHERE {where} RETURNING {columns(kind)}', values + ids))
    if kind == 'order':
        if body.status != 'pending':
            raise ApiError(400, 'INVALID_INITIAL_STATUS', 'New orders must have status pending.')
        placeholders = ', '.join(['%s'] * len(names))
        rows = query(f'''INSERT INTO orders ({', '.join(names)}, owner_id, offer_id, unit_price_eur)
            SELECT {placeholders}, %s, id, price_per_tonne_eur FROM offers WHERE id=%s AND available=true
            RETURNING {columns(kind)}''', values + [owner_id, parent_id])
        if not rows:
            raise ApiError(409, 'OFFER_UNAVAILABLE', 'Orders can only be created for an available offer.')
        return rows[0]
    if kind in PARENT:
        names.append(PARENT[kind])
        values.append(parent_id)
    if kind == 'quarry':
        names.append('owner_id')
        values.append(owner_id)
    placeholders = ', '.join(['%s'] * len(values))
    return required(query(f'INSERT INTO {TABLES[kind]} ({", ".join(names)}) VALUES ({placeholders}) '
                          f'RETURNING {columns(kind)}', values))


def delete(kind, item_id, parent_id=None):
    where, params = scope(kind, item_id, parent_id)
    required(query(f'DELETE FROM {TABLES[kind]} WHERE {where} RETURNING id', params))


def summary(quarry_id):
    return query('''SELECT
        (SELECT count(*)::int FROM offers WHERE quarry_id=%s) AS "offerCount",
        (SELECT count(*)::int FROM offers WHERE quarry_id=%s AND available) AS "availableOfferCount",
        count(r.id)::int AS "orderCount",
        count(r.id) FILTER (WHERE r.status='pending')::int AS "pendingOrderCount",
        COALESCE(sum(r.material_total_eur) FILTER (WHERE r.status <> 'cancelled'),0)::numeric AS "activeMaterialTotalEur"
        FROM orders r JOIN offers o ON o.id=r.offer_id WHERE o.quarry_id=%s''',
        [quarry_id, quarry_id, quarry_id])[0]
