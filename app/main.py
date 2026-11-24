import logging
from contextlib import asynccontextmanager

import psycopg
from psycopg_pool import PoolTimeout
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, Response
from starlette.routing import Match

from app.db import pool, query
from app.errors import ApiError
from app.routes import router
from app.auth import router as auth_router, check_secret


@asynccontextmanager
async def lifespan(_app):
    check_secret()
    pool.open()
    yield
    pool.close()


app = FastAPI(title='Noriuzvyro Lab1 API', version='2.0.0', lifespan=lifespan,
              description='Python + FastAPI + PostgreSQL. Same Lab1 Postman contract.',
              responses={400: {'description': 'Invalid input'}, 404: {'description': 'Resource not found'},
                         409: {'description': 'Conflict'}, 503: {'description': 'Database unavailable'}})
app.include_router(router)
app.include_router(auth_router)


def failure(status, code, message, details=None, headers=None):
    error = {'code': code, 'message': message}
    if details is not None:
        error['details'] = details
    return JSONResponse({'error': error}, status_code=status, headers=headers)


@app.exception_handler(ApiError)
async def api_error(_request, error):
    return failure(error.status, error.code, error.message,
                   headers={'WWW-Authenticate': 'Bearer'} if error.status == 401 else None)


@app.exception_handler(RequestValidationError)
async def validation_error(_request, error):
    return failure(400, 'VALIDATION_ERROR', 'Invalid request data.', [
        {'field': '.'.join(map(str, e['loc'])), 'message': e['msg']} for e in error.errors()])


@app.exception_handler(HTTPException)
async def http_error(request, error):
    codes = {404: 'NOT_FOUND', 405: 'METHOD_NOT_ALLOWED'}
    headers = dict(error.headers or {})
    if error.status_code == 405:
        headers['Allow'] = ', '.join(allowed_methods(request))
    return failure(error.status_code, codes.get(error.status_code, 'HTTP_ERROR'), str(error.detail), headers=headers)


@app.exception_handler(psycopg.Error)
async def database_error(_request, error):
    if error.sqlstate in ('23503', '23505'):
        return failure(409, 'CONFLICT', 'The operation conflicts with related or existing records. Delete child records first.')
    if error.sqlstate in ('23514', '23502', '22003', '22001', '22P02'):
        return failure(400, 'INVALID_DATA', 'Values violate database constraints.')
    if isinstance(error, psycopg.OperationalError) or error.sqlstate == '57014':
        return failure(503, 'DATABASE_UNAVAILABLE', 'Database is temporarily unavailable.')
    logging.exception('Unexpected database error')
    return failure(500, 'INTERNAL_ERROR', 'An unexpected server error occurred.')


@app.exception_handler(PoolTimeout)
async def pool_timeout(_request, _error):
    return failure(503, 'DATABASE_UNAVAILABLE', 'Database is temporarily unavailable.')


@app.exception_handler(Exception)
async def unexpected_error(_request, error):
    logging.error('Unexpected error', exc_info=error)
    return failure(500, 'INTERNAL_ERROR', 'An unexpected server error occurred.')


def allowed_methods(request):
    methods = set()
    for route in [*router.routes, *auth_router.routes, *app.routes]:
        match, _ = route.matches(request.scope)
        if match in (Match.FULL, Match.PARTIAL):
            methods.update(getattr(route, 'methods', set()))
    if methods:
        methods.add('OPTIONS')
    return sorted(methods)


@app.middleware('http')
async def request_policy(request: Request, call_next):
    if request.method == 'OPTIONS' and (methods := allowed_methods(request)):
        response = Response(status_code=204, headers={'Allow': ', '.join(methods)})
    elif request.method in ('POST', 'PUT', 'PATCH'):
        if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
            response = failure(415, 'UNSUPPORTED_MEDIA_TYPE', 'Send the body as application/json.')
        else:
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 32768:
                    break
            if len(body) > 32768:
                response = failure(413, 'BODY_TOO_LARGE', 'Maximum JSON body size is 32 KB.')
            else:
                request._body = bytes(body)  # replay the bounded body to FastAPI
                response = await call_next(request)
    else:
        response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.get('/health')
def health():
    query('SELECT 1')
    return {'status': 'ok', 'database': 'connected'}


# Separate, undocumented HEAD routes preserve the API without duplicate OpenAPI IDs.
for target in (router, app):
    for route in list(target.routes):
        if getattr(route, 'methods', None) and 'GET' in route.methods and hasattr(route, 'dependant'):
            # Router paths already contain /api; add_api_route prepends its prefix.
            path = route.path.removeprefix(router.prefix) if target is router else route.path
            target.add_api_route(path, route.endpoint, methods=['HEAD'], include_in_schema=False,
                                 dependencies=route.dependencies)
