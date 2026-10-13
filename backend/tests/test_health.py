"""Health and readiness probes."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readiness(client):
    r = client.get("/readiness")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["queue"] == "ok"
