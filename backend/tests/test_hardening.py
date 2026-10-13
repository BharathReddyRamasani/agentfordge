"""Production hardening: error envelope, request IDs, logout revocation, pagination."""

from tests.conftest import submit_requirement


def test_ready_alias(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["ready"] is True


def test_error_envelope_shape(client):
    r = client.get("/api/projects/999999", headers={"Authorization": "Bearer invalid"})
    assert r.status_code == 401
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "UNAUTHENTICATED"
    assert body["error"]["request_id"]
    assert "message" in body["error"]


def test_not_found_envelope_and_request_id_header(client, user_headers):
    r = client.get("/api/projects/999999", headers=user_headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
    assert r.headers.get("X-Request-ID") == r.json()["error"]["request_id"]


def test_validation_envelope(client):
    r = client.post("/api/auth/register", json={"email": "not-an-email", "name": "x", "password": "short"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_logout_revokes_token(client, user_headers):
    assert client.get("/api/auth/me", headers=user_headers).status_code == 200
    r = client.post("/api/auth/logout", headers=user_headers)
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=user_headers).status_code == 401
    assert client.get("/api/projects", headers=user_headers).status_code == 401


def test_planning_get_endpoint(client, user_headers, project):
    pid = project["id"]
    submit_requirement(client, user_headers, pid)
    assert client.get(f"/api/projects/{pid}/planning", headers=user_headers).status_code == 404
    client.post(f"/api/projects/{pid}/requirements/analyze", headers=user_headers)
    client.post(f"/api/projects/{pid}/planning", headers=user_headers)
    for path in (f"/api/projects/{pid}/planning", f"/api/projects/{pid}/plan"):
        r = client.get(path, headers=user_headers)
        assert r.status_code == 200, path
        assert r.json()["version"] == 1


def test_project_list_pagination(client, user_headers):
    for i in range(3):
        client.post("/api/projects", json={"name": f"P{i}", "description": "d"}, headers=user_headers)
    r = client.get("/api/projects?limit=2&offset=0", headers=user_headers).json()
    assert r["total"] >= 3 and len(r["items"]) == 2
    r2 = client.get("/api/projects?limit=2&offset=2", headers=user_headers).json()
    assert r2["total"] == r["total"]
    first_page = set(p["id"] for p in r["items"])
    second_page = set(p["id"] for p in r2["items"])
    assert first_page.isdisjoint(second_page)
