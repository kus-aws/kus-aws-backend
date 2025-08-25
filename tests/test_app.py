from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_echo_default():
    res = client.get("/api/v1/echo")
    assert res.status_code == 200
    assert res.json() == {"echo": "hello"}


def test_echo_query():
    res = client.get("/api/v1/echo", params={"q": "world"})
    assert res.status_code == 200
    assert res.json() == {"echo": "world"}


