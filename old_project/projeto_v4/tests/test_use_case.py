from fastapi.testclient import TestClient
from projeto_v3.app.main import app


def test_version():
    client = TestClient(app)
    r = client.get("/version")
    assert r.status_code == 200
    body = r.json()
    assert "version" in body and isinstance(body["version"], str)
