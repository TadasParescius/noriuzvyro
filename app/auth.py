"""JWT access tokens and rotating, hashed refresh tokens."""
import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import EmailStr, Field
from pwdlib import PasswordHash

from app.db import pool, query
from app.errors import ApiError
from app.schemas import Body

SECRET = os.getenv('JWT_SECRET', '')
ACCESS_SECONDS = int(os.getenv('ACCESS_TOKEN_SECONDS', '900'))
REFRESH_DAYS = 7
SECURE_COOKIE = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
ORIGINS = set(os.getenv('APP_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000').split(','))
passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))
bearer = HTTPBearer(auto_error=False)
router = APIRouter(prefix='/api/auth', tags=['Authentication'])


class RegisterBody(Body):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=10, max_length=128)


class LoginBody(Body):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)


class RoleBody(Body):
    role: Literal['buyer', 'quarry', 'driver', 'admin']


def check_secret():
    if len(SECRET) < 32:
        raise RuntimeError('Set JWT_SECRET to at least 32 random characters in .env.')


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def public_user(user):
    return {k: user[k] for k in ('id', 'name', 'email', 'role')}


def check_origin(request):
    origin = request.headers.get('origin')
    if origin and origin not in ORIGINS:
        raise ApiError(403, 'FORBIDDEN', 'Untrusted request origin.')
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise ApiError(403, 'FORBIDDEN', 'Cross-site authentication requests are not allowed.')


def token_response(user, sid, refresh, response):
    check_secret()
    now = datetime.now(timezone.utc)
    access = jwt.encode({'sub': str(user['id']), 'role': user['role'], 'sid': str(sid),
                         'type': 'access', 'iss': 'noriuzvyro', 'aud': 'noriuzvyro-api',
                         'iat': now, 'exp': now + timedelta(seconds=ACCESS_SECONDS)}, SECRET, algorithm='HS256')
    response.set_cookie('refresh_token', refresh, max_age=REFRESH_DAYS*86400, httponly=True,
                        secure=SECURE_COOKIE, samesite='strict', path='/api/auth')
    return {'accessToken': access, 'tokenType': 'bearer', 'expiresIn': ACCESS_SECONDS, 'user': public_user(user)}


def start_session(user, response):
    sid, refresh = uuid.uuid4(), secrets.token_urlsafe(48)
    with pool.connection() as conn:
        conn.execute('INSERT INTO auth_sessions(id,user_id,expires_at) VALUES(%s,%s,%s)',
                     (sid, user['id'], datetime.now(timezone.utc)+timedelta(days=REFRESH_DAYS)))
        conn.execute('INSERT INTO refresh_tokens(token_hash,session_id) VALUES(%s,%s)', (digest(refresh), sid))
    return token_response(user, sid, refresh, response)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise ApiError(401, 'UNAUTHORIZED', 'Prisijunkite prie paskyros.')
    try:
        claims = jwt.decode(credentials.credentials, SECRET, algorithms=['HS256'], audience='noriuzvyro-api',
                            issuer='noriuzvyro', options={'require': ['exp','iat','sub','sid','role','type']})
        if claims['type'] != 'access':
            raise ValueError()
        uid, sid = int(claims['sub']), uuid.UUID(claims['sid'])
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise ApiError(401, 'UNAUTHORIZED', 'Prisijungimas nebegalioja.') from None
    rows = query('''SELECT u.id,u.name,u.email,u.role,s.id AS session_id FROM users u
        JOIN auth_sessions s ON s.user_id=u.id
        WHERE u.id=%s AND s.id=%s AND NOT s.revoked AND s.expires_at>now()''', (uid, sid))
    if not rows or rows[0]['role'] != claims['role']:
        raise ApiError(401, 'UNAUTHORIZED', 'Prisijungimas nebegalioja.')
    return rows[0]


def require_role(user, *roles):
    if user['role'] not in roles:
        raise ApiError(403, 'FORBIDDEN', 'Šiam veiksmui neturite teisių.')


@router.post('/register', status_code=201)
def register(body: RegisterBody, request: Request, response: Response):
    check_origin(request)
    rows = query('''INSERT INTO users(name,email,password_hash) VALUES(%s,%s,%s)
        ON CONFLICT(email) DO NOTHING RETURNING id,name,email,role''',
        (body.name, str(body.email).lower(), passwords.hash(body.password)))
    if not rows:
        raise ApiError(409, 'EMAIL_EXISTS', 'Šis el. paštas jau užregistruotas.')
    return start_session(rows[0], response)


@router.post('/login')
def login(body: LoginBody, request: Request, response: Response):
    check_origin(request)
    rows = query('SELECT * FROM users WHERE email=%s', (str(body.email).lower(),))
    valid = passwords.verify(body.password, rows[0]['password_hash'] if rows else DUMMY_HASH)
    if not rows or not valid:
        raise ApiError(401, 'UNAUTHORIZED', 'Neteisingas el. paštas arba slaptažodis.')
    return start_session(rows[0], response)


@router.post('/refresh')
def refresh_token(request: Request, response: Response):
    check_origin(request)
    raw = request.cookies.get('refresh_token', '')
    replacement = secrets.token_urlsafe(48)
    invalid = False
    with pool.connection() as conn:
        row = conn.execute('''SELECT t.used,s.id,s.user_id,s.revoked,s.expires_at FROM refresh_tokens t
            JOIN auth_sessions s ON s.id=t.session_id WHERE t.token_hash=%s FOR UPDATE OF s,t''', (digest(raw),)).fetchone()
        if not row or row['revoked'] or row['expires_at'] <= datetime.now(timezone.utc):
            invalid = True
        elif row['used']:
            conn.execute('UPDATE auth_sessions SET revoked=true WHERE id=%s', (row['id'],))
            invalid = True
        else:
            conn.execute('UPDATE refresh_tokens SET used=true WHERE token_hash=%s', (digest(raw),))
            conn.execute('INSERT INTO refresh_tokens(token_hash,session_id) VALUES(%s,%s)', (digest(replacement), row['id']))
            user = conn.execute('SELECT id,name,email,role FROM users WHERE id=%s', (row['user_id'],)).fetchone()
    if invalid:
        raise ApiError(401, 'UNAUTHORIZED', 'Sesija pasibaigė. Prisijunkite iš naujo.')
    return token_response(user, row['id'], replacement, response)


@router.post('/logout', status_code=204)
def logout(request: Request, response: Response):
    check_origin(request)
    # Revoking the session invalidates both its access and refresh tokens.
    query('''UPDATE auth_sessions SET revoked=true WHERE id IN
        (SELECT session_id FROM refresh_tokens WHERE token_hash=%s) RETURNING id''',
        (digest(request.cookies.get('refresh_token','')),))
    response.delete_cookie('refresh_token', path='/api/auth', secure=SECURE_COOKIE, httponly=True, samesite='strict')
    response.status_code = 204
    return response


@router.get('/me')
def me(user=Depends(current_user)):
    return public_user(user)


@router.get('/users')
def list_users(user=Depends(current_user)):
    require_role(user, 'admin')
    return {'data': query('SELECT id,name,email,role FROM users ORDER BY id')}


@router.patch('/users/{user_id}/role')
def change_role(user_id: int, body: RoleBody, user=Depends(current_user)):
    require_role(user, 'admin')
    if user_id == user['id']:
        raise ApiError(400, 'INVALID_ROLE_CHANGE', 'Savo rolės keisti negalima.')
    with pool.connection() as conn:
        row = conn.execute('UPDATE users SET role=%s WHERE id=%s RETURNING id,name,email,role', (body.role,user_id)).fetchone()
        if not row:
            raise ApiError(404, 'NOT_FOUND', 'Naudotojas nerastas.')
        conn.execute('UPDATE auth_sessions SET revoked=true WHERE user_id=%s', (user_id,))
    return row
