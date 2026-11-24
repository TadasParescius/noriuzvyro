from math import ceil
from urllib.parse import urlencode


def link(href, method='GET'):
    return {'href': href, 'method': method}


def resource(row, kind, quarry_id=None):
    if kind == 'quarry':
        path = f'/api/quarries/{row["id"]}'
        related = {'collection': link('/api/quarries'), 'offers': link(path + '/offers'), 'summary': link(path + '/summary')}
        related['patch'] = link(path, 'PATCH')
    elif kind == 'offer':
        parent = f'/api/quarries/{row["quarryId"]}'
        path = f'{parent}/offers/{row["id"]}'
        related = {'quarry': link(parent), 'collection': link(parent + '/offers'), 'orders': link(path + '/orders')}
    else:
        parent = f'/api/quarries/{quarry_id}/offers/{row["offerId"]}'
        path = f'{parent}/orders/{row["id"]}'
        related = {'offer': link(parent), 'collection': link(parent + '/orders')}
    return {**row, '_links': {'self': link(path), 'update': link(path, 'PUT'), 'delete': link(path, 'DELETE'), **related}}


def paginated(request, rows, total, page, page_size):
    total_pages = ceil(total / page_size)
    params = dict(request.query_params)

    def page_link(number):
        return link(request.url.path + '?' + urlencode({**params, 'page': number, 'pageSize': page_size}))

    return {'data': rows, 'meta': {'total': total, 'page': page, 'pageSize': page_size, 'totalPages': total_pages},
            '_links': {'self': page_link(page), 'first': page_link(1), 'last': page_link(max(1, total_pages)),
                       'previous': page_link(page - 1) if page > 1 else None,
                       'next': page_link(page + 1) if page < total_pages else None,
                       'create': link(request.url.path, 'POST')}}
