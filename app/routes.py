from fastapi import APIRouter, Depends, Request, Response

from app import repository as db
from app.auth import current_user, require_role
from app.errors import ApiError
from app.schemas import Body
from typing import Literal
from pydantic import Field
from app.schemas import QuarryBody, QuarryPatchBody, OfferBody, OrderBody, filters, positive_id
from app.links import resource, paginated, link

router = APIRouter(prefix='/api')


def quarry_scope(quarry_id: str):
    return db.get('quarry', positive_id(quarry_id))


def offer_scope(offer_id: str, quarry=Depends(quarry_scope)):
    return db.get('offer', positive_id(offer_id), quarry['id'])


def order_scope(order_id: str, offer=Depends(offer_scope), quarry=Depends(quarry_scope), user=Depends(current_user)):
    order = db.get('order', positive_id(order_id), offer['id'])
    if user['role'] != 'admin' and user['id'] not in (order['ownerId'], order['driverId'], quarry['ownerId']):
        raise ApiError(403, 'FORBIDDEN', 'Šis užsakymas jums nepriklauso.')
    return order


def manage_quarry(quarry=Depends(quarry_scope), user=Depends(current_user)):
    require_role(user, 'admin', 'quarry')
    if user['role'] != 'admin' and quarry['ownerId'] != user['id']:
        raise ApiError(403, 'FORBIDDEN', 'Galite valdyti tik savo karjerą.')
    return quarry


def manage_offer(offer=Depends(offer_scope), _quarry=Depends(manage_quarry)):
    return offer


def manage_order(order=Depends(order_scope), user=Depends(current_user)):
    if user['role'] != 'admin' and order['ownerId'] != user['id']:
        raise ApiError(403, 'FORBIDDEN', 'Galite keisti tik savo užsakymą.')
    if user['role'] != 'admin' and order['status'] != 'pending':
        raise ApiError(409, 'ORDER_LOCKED', 'Keisti galima tik laukiančius užsakymus.')
    return order


def no_query(request: Request):
    filters(request)


def listing(request, kind, parent_id=None, quarry_id=None, user=None):
    options = filters(request, kind)
    result = db.list_records(kind, options, parent_id, user)
    return paginated(request, [resource(row, kind, quarry_id) for row in result['data']],
                     result['total'], options['page'], options['pageSize'])


def created(response, row, kind, quarry_id=None):
    result = resource(row, kind, quarry_id)
    response.headers['Location'] = result['_links']['self']['href']
    return result


@router.get('')
def api_root():
    return {'name': 'Noriuzvyro Lab1 API', 'version': '2.0.0', '_links': {
        'self': link('/api'), 'quarries': link('/api/quarries'), 'health': link('/health')}}


@router.get('/quarries')
def list_quarries(request: Request):
    return listing(request, 'quarry')


@router.post('/quarries', status_code=201, dependencies=[Depends(no_query)])
def create_quarry(body: QuarryBody, response: Response, user=Depends(current_user)):
    require_role(user, 'admin', 'quarry')
    return created(response, db.save('quarry', body, owner_id=user['id']), 'quarry')


@router.get('/quarries/{quarry_id}', dependencies=[Depends(no_query)])
def read_quarry(quarry=Depends(quarry_scope)):
    return resource(quarry, 'quarry')


@router.put('/quarries/{quarry_id}', dependencies=[Depends(no_query)])
def update_quarry(body: QuarryBody, quarry=Depends(manage_quarry)):
    return resource(db.save('quarry', body, item_id=quarry['id']), 'quarry')

@router.patch('/quarries/{quarry_id}', dependencies=[Depends(no_query)])
def patch_quarry(body: QuarryPatchBody, quarry=Depends(manage_quarry)):
    return resource(db.patch('quarry', body, quarry['id']), 'quarry')


@router.delete('/quarries/{quarry_id}', status_code=204, dependencies=[Depends(no_query)])
def delete_quarry(quarry=Depends(manage_quarry)):
    db.delete('quarry', quarry['id'])
    return Response(status_code=204)


@router.get('/quarries/{quarry_id}/summary', dependencies=[Depends(no_query)])
def quarry_summary(quarry=Depends(manage_quarry)):
    path = f'/api/quarries/{quarry["id"]}'
    return {'quarry': resource(quarry, 'quarry'), 'statistics': db.summary(quarry['id']),
            '_links': {'self': link(path + '/summary'), 'offers': link(path + '/offers')}}


@router.get('/quarries/{quarry_id}/offers')
def list_offers(request: Request, quarry=Depends(quarry_scope)):
    return listing(request, 'offer', quarry['id'])


@router.post('/quarries/{quarry_id}/offers', status_code=201, dependencies=[Depends(no_query)])
def create_offer(body: OfferBody, response: Response, quarry=Depends(manage_quarry)):
    return created(response, db.save('offer', body, quarry['id']), 'offer')


@router.get('/quarries/{quarry_id}/offers/{offer_id}', dependencies=[Depends(no_query)])
def read_offer(offer=Depends(offer_scope)):
    return resource(offer, 'offer')


@router.put('/quarries/{quarry_id}/offers/{offer_id}', dependencies=[Depends(no_query)])
def update_offer(body: OfferBody, offer=Depends(manage_offer)):
    return resource(db.save('offer', body, offer['quarryId'], offer['id']), 'offer')


@router.delete('/quarries/{quarry_id}/offers/{offer_id}', status_code=204, dependencies=[Depends(no_query)])
def delete_offer(offer=Depends(manage_offer)):
    db.delete('offer', offer['id'], offer['quarryId'])
    return Response(status_code=204)


@router.get('/quarries/{quarry_id}/offers/{offer_id}/orders')
def list_orders(request: Request, offer=Depends(offer_scope), user=Depends(current_user)):
    return listing(request, 'order', offer['id'], offer['quarryId'], user)


@router.post('/quarries/{quarry_id}/offers/{offer_id}/orders', status_code=201, dependencies=[Depends(no_query)])
def create_order(body: OrderBody, response: Response, offer=Depends(offer_scope), user=Depends(current_user)):
    require_role(user, 'buyer', 'admin')
    return created(response, db.save('order', body, offer['id'], owner_id=user['id']), 'order', offer['quarryId'])


@router.get('/quarries/{quarry_id}/offers/{offer_id}/orders/{order_id}', dependencies=[Depends(no_query)])
def read_order(order=Depends(order_scope), offer=Depends(offer_scope)):
    return resource(order, 'order', offer['quarryId'])


@router.put('/quarries/{quarry_id}/offers/{offer_id}/orders/{order_id}', dependencies=[Depends(no_query)])
def update_order(body: OrderBody, order=Depends(manage_order), offer=Depends(offer_scope), user=Depends(current_user)):
    if user['role'] != 'admin' and body.status != 'pending':
        raise ApiError(403, 'FORBIDDEN', 'Užsakymo būseną keičia karjeras arba administratorius.')
    return resource(db.save('order', body, offer['id'], order['id']), 'order', offer['quarryId'])


@router.delete('/quarries/{quarry_id}/offers/{offer_id}/orders/{order_id}', status_code=204, dependencies=[Depends(no_query)])
def delete_order(order=Depends(manage_order)):
    db.delete('order', order['id'], order['offerId'])
    return Response(status_code=204)


class StatusBody(Body):
    status: Literal['pending', 'confirmed', 'delivered', 'cancelled']


class AssignBody(Body):
    driverId: int = Field(gt=0)


@router.patch('/quarries/{quarry_id}/offers/{offer_id}/orders/{order_id}/status')
def order_status(body: StatusBody, order=Depends(order_scope), quarry=Depends(quarry_scope), user=Depends(current_user)):
    allowed = {'pending': {'confirmed', 'cancelled'}, 'confirmed': {'delivered', 'cancelled'}}
    if user['role'] == 'driver':
        if order['driverId'] != user['id'] or body.status != 'delivered' or order['status'] != 'confirmed':
            raise ApiError(403, 'FORBIDDEN', 'Galite pažymėti tik savo patvirtinto pristatymo įvykdymą.')
    elif user['role'] == 'quarry':
        if quarry['ownerId'] != user['id']:
            raise ApiError(403, 'FORBIDDEN', 'Tai ne jūsų karjero užsakymas.')
    elif user['role'] != 'admin':
        raise ApiError(403, 'FORBIDDEN', 'Negalite keisti būsenos.')
    if user['role'] != 'admin' and body.status not in allowed.get(order['status'], set()):
        raise ApiError(409, 'INVALID_TRANSITION', 'Šis būsenos pakeitimas negalimas.')
    return resource(db.patch('order', body, order['id'], order['offerId']), 'order', quarry['id'])


@router.patch('/quarries/{quarry_id}/offers/{offer_id}/orders/{order_id}/driver')
def assign_driver(body: AssignBody, order=Depends(order_scope), quarry=Depends(manage_quarry)):
    drivers = db.query("SELECT id FROM users WHERE id=%s AND role='driver'", (body.driverId,))
    if not drivers:
        raise ApiError(400, 'INVALID_DRIVER', 'Vairuotojas nerastas.')
    db.query('UPDATE orders SET driver_id=%s,updated_at=now() WHERE id=%s RETURNING id', (body.driverId,order['id']))
    return resource(db.get('order',order['id'],order['offerId']), 'order',quarry['id'])


@router.get('/drivers')
def drivers(user=Depends(current_user)):
    require_role(user, 'quarry', 'admin')
    return {'data': db.query("SELECT id,name FROM users WHERE role='driver' ORDER BY name")}


@router.get('/my/orders')
def my_orders(user=Depends(current_user)):
    # Private dashboard: no customer contact data is returned to unrelated users.
    rows = db.query("""SELECT r.id,r.offer_id AS "offerId",o.quarry_id AS "quarryId"
        FROM orders r JOIN offers o ON o.id=r.offer_id JOIN quarries q ON q.id=o.quarry_id
        WHERE %s='admin' OR r.owner_id=%s OR r.driver_id=%s OR q.owner_id=%s ORDER BY r.id DESC""",
        (user['role'],user['id'],user['id'],user['id']))
    return {'data': [resource(db.get('order',r['id'],r['offerId']), 'order',r['quarryId']) for r in rows]}
