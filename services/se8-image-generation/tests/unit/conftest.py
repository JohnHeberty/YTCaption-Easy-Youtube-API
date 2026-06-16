import pytest
import respx

from app.services.image_service import FooocusClient


@pytest.fixture
def fooocus_client():
    return FooocusClient()


@pytest.fixture
def mock_fooocus():
    with respx.mock:
        respx.mock.base_url = "http://mock-fooocus:8888"
        yield respx
