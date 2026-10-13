"""Project CRUD and notifications."""


def test_project_crud(client, user_headers):
    r = client.post("/api/projects", json={"name": "P1", "description": "desc"}, headers=user_headers)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["status"] == "CREATED"

    r = client.get("/api/projects", headers=user_headers)
    assert r.json()["total"] >= 1

    r = client.get(f"/api/projects/{pid}", headers=user_headers)
    assert r.status_code == 200

    r = client.get(f"/api/projects/{pid}/workflow", headers=user_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "CREATED"
    assert len(r.json()["stages"]) == 13

    assert client.delete(f"/api/projects/{pid}", headers=user_headers).status_code == 204
    assert client.get(f"/api/projects/{pid}", headers=user_headers).status_code == 404


def test_notifications_flow(client, user_headers, project):
    from tests.conftest import submit_requirement

    pid = project["id"]
    submit_requirement(client, user_headers, pid)
    client.post(f"/api/projects/{pid}/requirements/analyze", headers=user_headers)
    client.post(f"/api/projects/{pid}/planning", headers=user_headers)
    client.post(f"/api/projects/{pid}/prototype/generate", headers=user_headers)

    r = client.get("/api/notifications", headers=user_headers)
    assert r.status_code == 200
    assert any("review" in n["title"].lower() or "prototype" in n["title"].lower() for n in r.json())

    nid = r.json()[0]["id"]
    assert client.post(f"/api/notifications/{nid}/read", headers=user_headers).status_code == 200
    r = client.get("/api/notifications?unread_only=true", headers=user_headers)
    assert all(n["id"] != nid for n in r.json())
