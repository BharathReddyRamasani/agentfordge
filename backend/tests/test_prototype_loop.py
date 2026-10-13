"""THE key workflow test: requirement → analyze → plan → prototype → feedback →
plan revision → prototype rebuild → approval. Runs inline (sync worker, mock LLM)."""

from tests.conftest import HOSPITAL_REQUIREMENT, submit_requirement


def test_full_prototype_validation_loop(client, user_headers, project):
    pid = project["id"]

    submit_requirement(client, user_headers, pid)

    # Analyze
    r = client.post(f"/api/projects/{pid}/requirements/analyze", headers=user_headers)
    assert r.status_code == 202, r.text
    r = client.get(f"/api/projects/{pid}/analysis", headers=user_headers)
    assert r.status_code == 200, r.text
    analysis = r.json()["analysis"]
    assert "hospital" in analysis["project_name"].lower()
    assert len(analysis["essential_features"]) >= 3
    assert len(analysis["primary_user_flow"]) >= 2

    w = client.get(f"/api/projects/{pid}/workflow", headers=user_headers).json()
    assert w["status"] == "PLANNING"

    # Plan
    r = client.post(f"/api/projects/{pid}/planning", headers=user_headers)
    assert r.status_code == 202, r.text
    r = client.get(f"/api/projects/{pid}/plan", headers=user_headers)
    assert r.status_code == 200, r.text
    plan = r.json()["plan"]
    assert len(plan["prototype_scope"]["screens"]) >= 2

    # Prototype v1
    r = client.post(f"/api/projects/{pid}/prototype/generate", headers=user_headers)
    assert r.status_code == 202, r.text
    r = client.get(f"/api/projects/{pid}/prototype", headers=user_headers)
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 1
    assert len(r.json()["spec"]["screens"]) >= 2

    # Preview serves real HTML
    token = user_headers["Authorization"].split(" ", 1)[1]
    r = client.get(f"/api/projects/{pid}/prototype/preview?token={token}")
    assert r.status_code == 200
    assert "<html" in r.text.lower()
    assert "prototype" in r.text.lower()

    w = client.get(f"/api/projects/{pid}/workflow", headers=user_headers).json()
    assert w["status"] == "AWAITING_REVIEW"

    # Feedback → plan revision + rebuild → v2
    r = client.post(
        f"/api/projects/{pid}/prototype/feedback",
        json={"feedback": "Add order tracking and an admin dashboard. Patients should be able to cancel appointments."},
        headers=user_headers,
    )
    assert r.status_code == 202, r.text
    r = client.get(f"/api/projects/{pid}/prototype", headers=user_headers)
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 2, r.json()

    r = client.get(f"/api/projects/{pid}/plan", headers=user_headers)
    assert r.json()["version"] == 2
    assert "feedback" in r.json()["plan"].get("revision_notes", "").lower()

    versions = client.get(f"/api/projects/{pid}/prototype/versions", headers=user_headers).json()
    assert [v["version"] for v in versions] == [1, 2]

    # Approve
    r = client.post(f"/api/projects/{pid}/prototype/approve", json={"comment": "Looks good"}, headers=user_headers)
    assert r.status_code == 200, r.text
    w = client.get(f"/api/projects/{pid}/workflow", headers=user_headers).json()
    assert w["status"] == "APPROVED"

    # Agent activity + logs recorded
    agents = client.get(f"/api/projects/{pid}/agents", headers=user_headers).json()
    assert len(agents) >= 4
    logs = client.get(f"/api/projects/{pid}/logs", headers=user_headers).json()
    assert len(logs) >= 10

    # Memory (RAG) has indexed the loop artifacts
    mem = client.get(f"/api/projects/{pid}/memory?q=appointment", headers=user_headers).json()
    assert len(mem) >= 1


def test_shortcut_analysis_plan_prototype_endpoints(client, user_headers, project):
    from tests.conftest import submit_requirement

    pid = project["id"]
    submit_requirement(client, user_headers, pid)
    assert client.post(f"/api/projects/{pid}/requirements", json={"description": HOSPITAL_REQUIREMENT}, headers=user_headers).status_code == 201
    assert client.get(f"/api/projects/{pid}/analysis", headers=user_headers).status_code == 404
    assert client.get(f"/api/projects/{pid}/plan", headers=user_headers).status_code == 404
    assert client.get(f"/api/projects/{pid}/prototype", headers=user_headers).status_code == 404
