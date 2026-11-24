class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def required(rows):
    if not rows:
        raise ApiError(404, 'NOT_FOUND', 'The resource does not exist within this parent.')
    return rows[0]
