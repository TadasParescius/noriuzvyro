import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope='session', autouse=True)
def application_lifespan():
    with TestClient(app):
        yield
