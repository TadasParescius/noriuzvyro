"""Authentication, session revocation and object ownership regression tests."""
import uuid
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import pool
from app.auth import SECRET

Q=dict(name='Auth quarry',city='Kaunas',address='Test street 20',phone='+37060000999',description='Authorization test quarry.',latitude=54,longitude=25)
O=dict(name='Auth sand',materialType='sand',fraction='0-2',description='Authorization test offer.',pricePerTonneEur=10,available=True)
R=dict(customerName='Test Buyer',email='buyer@example.com',phone='+37060000999',deliveryAddress='Test street 20',quantityTonnes=2,willBeHome=True,unloadingInstructions='',paymentMethod='cash',status='pending')

@pytest.fixture
def accounts():
    users=[]
    client = TestClient(app)
    def create(role='buyer'):
        email=f'{uuid.uuid4()}@example.com'
        body=dict(name='Auth Test',email=email,password='Secure-test-1234')
        result=client.post('/api/auth/register',json=body)
        assert result.status_code==201,result.text
        uid=result.json()['user']['id'];users.append(uid)
        if role!='buyer':
            with pool.connection() as conn: conn.execute('UPDATE users SET role=%s WHERE id=%s',(role,uid))
        result=client.post('/api/auth/login',json={'email':email,'password':body['password']})
        return result.json(),{'Authorization':'Bearer '+result.json()['accessToken']}
    yield client,create
    with pool.connection() as conn:
        conn.execute('DELETE FROM orders WHERE owner_id=ANY(%s) OR offer_id IN (SELECT o.id FROM offers o JOIN quarries q ON q.id=o.quarry_id WHERE q.owner_id=ANY(%s))',(users,users))
        conn.execute('DELETE FROM offers WHERE quarry_id IN (SELECT id FROM quarries WHERE owner_id=ANY(%s))',(users,))
        conn.execute('DELETE FROM quarries WHERE owner_id=ANY(%s)',(users,))
        conn.execute('DELETE FROM users WHERE id=ANY(%s)',(users,))


def test_registration_rotation_logout_and_replay(accounts):
    c,create=accounts
    data,headers=create()
    uid=data['user']['id']
    claims=jwt.decode(data['accessToken'],SECRET,algorithms=['HS256'],audience='noriuzvyro-api',issuer='noriuzvyro')
    assert claims['sub']==str(uid) and claims['role']=='buyer'
    assert claims['exp']-claims['iat']==900
    cookie=c.cookies.get('refresh_token')
    rotated=c.post('/api/auth/refresh',json={})
    assert rotated.status_code==200
    assert c.cookies.get('refresh_token')!=cookie
    assert 'HttpOnly' in rotated.headers['set-cookie'] and 'SameSite=strict' in rotated.headers['set-cookie']
    assert c.get('/api/auth/me',headers=headers).status_code==200
    c.cookies.clear();c.cookies.set('refresh_token',cookie)
    assert c.post('/api/auth/refresh',json={}).status_code==401
    assert c.get('/api/auth/me',headers=headers).status_code==401
    c.cookies.clear()
    data,headers=create()
    assert c.post('/api/auth/logout',json={}).status_code==204
    assert c.get('/api/auth/me',headers=headers).status_code==401
    assert c.post('/api/auth/refresh',json={}).status_code==401


def test_invalid_credentials_tokens_and_origin(accounts):
    c,create=accounts
    data,headers=create()
    assert c.post('/api/auth/register',json=dict(name='Bad',email='bad@example.com',password='long-password',role='admin')).status_code==400
    assert c.post('/api/auth/login',json=dict(email=data['user']['email'],password='wrong')).status_code==401
    assert c.get('/api/auth/me').status_code==401
    assert c.get('/api/auth/me',headers={'Authorization':'Bearer invalid'}).status_code==401
    claims=jwt.decode(data['accessToken'],SECRET,algorithms=['HS256'],audience='noriuzvyro-api')
    claims['exp']=datetime.now(timezone.utc)-timedelta(seconds=1)
    expired=jwt.encode(claims,SECRET,algorithm='HS256')
    assert c.get('/api/auth/me',headers={'Authorization':'Bearer '+expired}).status_code==401
    assert c.post('/api/auth/refresh',json={},headers={'Origin':'https://attacker.example'}).status_code==403


@pytest.mark.parametrize('status', ['confirmed', 'delivered', 'cancelled'])
def test_buyer_cannot_choose_advanced_initial_order_status(accounts, status):
    """Reject status escalation through POST before an order is stored."""
    c, create = accounts
    admin, ha = create('admin')
    buyer, hb = create()
    quarry = c.post('/api/quarries', json=Q, headers=ha).json()
    path = f'/api/quarries/{quarry["id"]}/offers'
    offer = c.post(path, json=O, headers=ha).json()
    orders = path + f'/{offer["id"]}/orders'
    rejected = c.post(orders, json={**R, 'status': status}, headers=hb)
    assert rejected.status_code == 400
    assert rejected.json()['error']['code'] == 'INVALID_INITIAL_STATUS'
    assert c.get(orders, headers=ha).json()['data'] == []
    pending = c.post(orders, json=R, headers=hb)
    assert pending.status_code == 201
    assert pending.json()['status'] == 'pending'
    assert pending.json()['ownerId'] == buyer['user']['id']
    assert c.post(orders, json={**R, 'status': status}, headers=ha).status_code == 400


def test_roles_ownership_and_private_orders(accounts):
    c,create=accounts
    admin,ha=create('admin'); quarry,hq=create('quarry'); other,ho=create('quarry')
    buyer,hb=create(); stranger,hs=create(); driver,hd=create('driver')
    assert c.post('/api/quarries',json=Q).status_code==401
    assert c.post('/api/quarries',json=Q,headers=hb).status_code==403
    q=c.post('/api/quarries',json=Q,headers=hq).json();qp=f'/api/quarries/{q["id"]}'
    assert c.put(qp,json=Q,headers=ho).status_code==403
    assert c.patch(qp,json={'name':'Stolen'},headers=hb).status_code==403
    assert c.delete(qp,headers=ho).status_code==403
    offer=c.post(qp+'/offers',json=O,headers=hq).json();op=qp+f'/offers/{offer["id"]}'
    assert c.put(op,json=O,headers=ho).status_code==403
    order=c.post(op+'/orders',json=R,headers=hb).json();rp=op+f'/orders/{order["id"]}'
    assert c.get(rp).status_code==401
    assert c.get(rp,headers=hs).status_code==403
    assert c.get(op+'/orders',headers=hs).json()['data']==[]
    assert c.get('/api/my/orders',headers=hs).json()['data']==[]
    assert c.put(rp,json=R,headers=hs).status_code==403
    assert c.put(rp,json={**R,'status':'delivered'},headers=hb).status_code==403
    assert c.get(qp+'/summary',headers=ho).status_code==403
    assert c.patch(rp+'/driver',json={'driverId':driver['user']['id']},headers=hq).status_code==200
    assert c.get(rp,headers=hd).status_code==200
    assert c.patch(rp+'/status',json={'status':'confirmed'},headers=hq).status_code==200
    assert c.put(rp,json=R,headers=hb).status_code==409
    assert c.patch(rp+'/status',json={'status':'delivered'},headers=hd).status_code==200
    assert c.delete(rp,headers=hd).status_code==403
    assert c.get('/api/auth/users',headers=hb).status_code==403
    assert c.patch(f'/api/auth/users/{buyer["user"]["id"]}/role',json={'role':'admin'},headers=hb).status_code==403
    assert c.patch(f'/api/auth/users/{buyer["user"]["id"]}/role',json={'role':'quarry'},headers=ha).status_code==200
    assert c.get('/api/auth/me',headers=hb).status_code==401
