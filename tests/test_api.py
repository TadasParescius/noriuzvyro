import pytest
import uuid
from app.auth import passwords, start_session
from starlette.responses import Response
from fastapi.testclient import TestClient

from app.main import app
from app.db import pool

QUARRY = dict(name='Python test quarry', city='Test city', address='Test road 10', phone='+37060000999',
              description='Integration test quarry.', latitude=54.9, longitude=23.9)
OFFER = dict(name='Test sand', materialType='sand', fraction='0-2 mm', description='Clean test sand.',
             pricePerTonneEur=12.35, available=True)
ORDER = dict(customerName='Test Customer', email='test@example.com', phone='+37060000998',
             deliveryAddress='Test street 20', quantityTonnes=2.5, willBeHome=False,
             unloadingInstructions='Leave beside the gate.', paymentMethod='cash', status='pending')


@pytest.fixture(scope='module')
def client():
    client = TestClient(app)
    with pool.connection() as conn:
        user = conn.execute("INSERT INTO users(name,email,password_hash,role) VALUES(%s,%s,%s,'admin') RETURNING id,name,email,role",
            ('Test administrator',f'{uuid.uuid4()}@example.com',passwords.hash('Testing-password-123'))).fetchone()
    tokens = start_session(user, Response())
    client.headers['Authorization'] = 'Bearer ' + tokens['accessToken']
    yield client
    with pool.connection() as conn:
        conn.execute('DELETE FROM users WHERE id=%s', (user['id'],))


@pytest.fixture
def records(client):
    ids = []
    def create():
        r = client.post('/api/quarries', json=QUARRY)
        assert r.status_code == 201, r.text
        ids.append(r.json()['id'])
        return r.headers['location']
    yield create
    with pool.connection() as conn:
        conn.execute('DELETE FROM orders WHERE offer_id IN (SELECT id FROM offers WHERE quarry_id=ANY(%s))', [ids])
        conn.execute('DELETE FROM offers WHERE quarry_id=ANY(%s)', [ids])
        conn.execute('DELETE FROM quarries WHERE id=ANY(%s)', [ids])


def checked(client, method, url, status, body=None):
    r = client.request(method, url, **({'json': body} if body is not None else {}))
    assert r.status_code == status, r.text
    return r


def test_crud_links_scoping_prices_and_summary(client, records):
    q, other = records(), records()
    assert client.get(q).json()['_links']['self']['href'] == q
    checked(client, 'PUT', q, 200, {**QUARRY, 'description': 'Changed description.'})
    o = checked(client, 'POST', q + '/offers', 201, OFFER).headers['location']
    oid = o.rsplit('/', 1)[-1]
    for method in ('GET', 'PUT', 'DELETE'):
        checked(client, method, other + '/offers/' + oid, 404, OFFER if method == 'PUT' else None)
    checked(client, 'GET', other + '/offers/' + oid + '/orders', 404)
    checked(client, 'POST', other + '/offers/' + oid + '/orders', 404, ORDER)
    response = checked(client, 'POST', o + '/orders', 201, ORDER)
    r = response.headers['location']
    assert response.json()['materialTotalEur'] == 30.88
    other_offer = checked(client, 'POST', q + '/offers', 201, OFFER).headers['location']
    wrong_order = other_offer + '/orders/' + r.rsplit('/', 1)[-1]
    for method in ('GET', 'PUT', 'DELETE'):
        checked(client, method, wrong_order, 404, ORDER if method == 'PUT' else None)
    checked(client, 'PUT', o, 200, {**OFFER, 'pricePerTonneEur': 99})
    changed = checked(client, 'PUT', r, 200, {**ORDER, 'quantityTonnes': 3, 'status': 'confirmed'}).json()
    assert changed['unitPriceEur'] == 12.35
    assert changed['materialTotalEur'] == 37.05
    summary = client.get(q + '/summary').json()
    assert summary['statistics']['orderCount'] == 1
    assert summary['statistics']['activeMaterialTotalEur'] == 37.05
    checked(client, 'DELETE', q, 409)
    checked(client, 'DELETE', o, 409)
    assert checked(client, 'DELETE', r, 204).content == b''
    checked(client, 'GET', r, 404)
    checked(client, 'DELETE', o, 204)
    checked(client, 'DELETE', other_offer, 204)
    checked(client, 'DELETE', q, 204)
    checked(client, 'GET', q, 404)


def test_pagination_filters_and_unavailable_offer(client, records):
    q, _ = records(), records()
    page = client.get('/api/quarries?city=Test%20city&pageSize=1').json()
    assert page['meta']['total'] == 2
    assert len(page['data']) == 1
    page2 = client.get(page['_links']['next']['href']).json()
    assert page2['data'][0]['id'] != page['data'][0]['id']
    assert client.get('/api/quarries?city=Test%20city&page=500').json()['data'] == []
    assert client.get('/api/quarries', params={'city': "' OR 1=1 --"}).json()['meta']['total'] == 0
    o = checked(client, 'POST', q + '/offers', 201, OFFER).headers['location']
    assert client.get(q + '/offers?materialType=sand&minPrice=12&maxPrice=13').json()['meta']['total'] == 1
    checked(client, 'PUT', o, 200, {**OFFER, 'available': False})
    checked(client, 'POST', o + '/orders', 409, ORDER)
    assert client.get(q + '/offers?available=true').json()['meta']['total'] == 0
    checked(client, 'PUT', o, 200, OFFER)
    checked(client, 'POST', o + '/orders', 201, ORDER)
    assert client.get(o + '/orders?status=pending&paymentMethod=cash').json()['meta']['total'] == 1
    assert client.get(o + '/orders?status=confirmed').json()['meta']['total'] == 0


@pytest.mark.parametrize('suffix', ['/abc', '/0', '/2147483648', '?page=0', '?page=-1', '?page=1.5',
                                    '?pageSize=101', '?pageSize=x', '?page=1&page=2', '?sort=bad'])
def test_invalid_path_and_query(client, suffix):
    checked(client, 'GET', '/api/quarries' + suffix, 400)


def test_body_validation_and_errors(client, records):
    q = records()
    o = checked(client, 'POST', q + '/offers', 201, OFFER).headers['location']
    for change in [dict(quantityTonnes=0), dict(quantityTonnes='5'), dict(quantityTonnes=True),
                   dict(quantityTonnes=1001), dict(quantityTonnes=1.0001), dict(email='wrong'),
                   dict(unloadingInstructions=''), dict(status='confirmed'), dict(unitPriceEur=1)]:
        checked(client, 'POST', o + '/orders', 400, {**ORDER, **change})
    for change in [dict(id=9), dict(latitude=100), dict(phone='wrong')]:
        checked(client, 'POST', '/api/quarries', 400, {**QUARRY, **change})
    checked(client, 'PUT', o, 400, {'name': 'Partial body'})
    checked(client, 'GET', q + '/offers?minPrice=20&maxPrice=10', 400)
    checked(client, 'GET', q + '/offers?available=maybe', 400)
    checked(client, 'POST', q + '/offers', 400, {**OFFER, 'pricePerTonneEur': 1.234})
    assert client.post('/api/quarries', content='{broken', headers={'Content-Type': 'application/json'}).status_code == 400
    assert client.post('/api/quarries', content='text', headers={'Content-Type': 'text/plain'}).status_code == 415
    checked(client, 'POST', '/api/quarries', 413, {**QUARRY, 'description': 'a' * 40000})
    assert 'PUT' in checked(client, 'PATCH', o, 405, {}).headers['allow']
    checked(client, 'GET', '/api/quarries/2147483647', 404)
    checked(client, 'GET', '/missing', 404)


def test_quarry_patch(client, records):
    q = records()
    before = client.get(q).json()
    changed = checked(client, 'PATCH', q, 200, {'name': 'Patched quarry'}).json()
    assert changed['name'] == 'Patched quarry'
    for field in (*QUARRY, 'id', 'createdAt'):
        if field != 'name':
            assert changed[field] == before[field]
    assert client.get(q).json() == changed
    assert changed['_links']['patch'] == {'href': q, 'method': 'PATCH'}
    assert 'PATCH' in client.options(q).headers['allow']
    changed = checked(client, 'PATCH', q, 200, {'latitude': 0, 'longitude': 0}).json()
    assert changed['latitude'] == changed['longitude'] == 0
    for body in ({}, {'id': 1}, {'name': 'A'}, {'phone': 'wrong'},
                 {'latitude': 91}, {'longitude': '25'}, {'city': ' '}):
        checked(client, 'PATCH', q, 400, body)
    for field in QUARRY:
        checked(client, 'PATCH', q, 400, {field: None})
    assert client.get(q).json() == changed
    checked(client, 'PUT', q, 400, {'name': 'Partial PUT'})
    checked(client, 'DELETE', q, 204)
    checked(client, 'PATCH', q, 404, {'name': 'Missing quarry'})


def test_patch_column_mapping(client, records):
    from app import repository
    from pydantic import BaseModel

    class OfferPricePatch(BaseModel):
        pricePerTonneEur: int

    q = records()
    offer = checked(client, 'POST', q + '/offers', 201, OFFER).json()
    updated = repository.patch('offer', OfferPricePatch(pricePerTonneEur=18),
                               offer['id'], offer['quarryId'])
    assert updated['pricePerTonneEur'] == 18
    assert updated['name'] == offer['name']


def test_health_docs_and_options(client):
    assert checked(client, 'GET', '/health', 200).headers['Cache-Control'] == 'no-store'
    assert 'POST' in checked(client, 'OPTIONS', '/api/quarries', 204).headers['allow']
    assert client.head('/health').status_code == 200
    assert client.get('/openapi.json').status_code == 200
    assert client.get('/docs').status_code == 200
