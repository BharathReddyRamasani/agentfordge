"""Approval-gate, state-guard, ownership, cancel/retry, and duplicate-action tests."""

import uuid

from tests.conftest import auth_headers_for, submit_requirement


def test_engineering_blocked_before_approval(client, user_headers, project):
    pid = project["id"]
    r = client.post(f"/api/projects/{pid}/engineering/start", headers=user_headers)
    assert r.status_code == 409


def test_feedback_rejected_outside_review(client, user_headers, project):
    pid = project["id"]
    r = client.post(f"/api/projects/{pid}/prototype/feedback", json={"feedback": "change x"}, headers=user_headers)
    assert r.status_code == 409


def test_approve_rejected_outside_review(client, user_headers, project):
    pid = project["id"]
    r = client.post(f"/api/projects/{pid}/prototype/approve", json={}, headers=user_headers)
    assert r.status_code == 409


def test_approve_without_prototype_rejected(client, user_headers, project):
    pid = project["id"]
    submit_requirement(client, user_headers, pid)
    assert client.post(f"/api/projects/{pid}/requirements/analyze", headers=user_headers).status_code == 202
    # status is now PLANNING, not a review state
    r = client.post(f"/api/projects/{pid}/prototype/approve", json={}, headers=user_headers)
    assert r.status_code == 409


def test_duplicate_approval_rejected(client, user_headers, project):
    pid = project["id"]
    submit_requirement(client, user_headers, pid)
    client.post(f"/api/projects/{pid}/requirements/analyze", headers=user_headers)
    client.post(f"/api/projects/{pid}/planning", headers=user_headers)
    client.post(f"/api/projects/{pid}/prototype/generate", headers=user_headers)
    assert client.post(f"/api/projects/{pid}/prototype/approve", json={}, headers=user_headers).status_code == 200
    # second approval of the same prototype version must be rejected
    r = client.post(f"/api/projects/{pid}/prototype/approve", json={}, headers=user_headers)
    assert r.status_code == 409


def test_project_ownership_enforced(client, user_headers, project):
    pid = project["id"]
    other = auth_headers_for(client, f"other_{uuid.uuid4().hex[:8]}@example.com")
    assert client.get(f"/api/projects/{pid}", headers=other).status_code == 403
    assert client.post(f"/api/projects/{pid}/requirements/analyze", headers=other).status_code == 403
    assert client.delete(f"/api/projects/{pid}", headers=other).status_code == 403
    assert client.get(f"/api/projects/{pid}/workflow", headers=other).status_code == 403


def test_cancel_and_retry(client, user_headers, project):
    pid = project["id"]
    # nothing running on a fresh project
    assert client.post(f"/api/projects/{pid}/cancel", headers=user_headers).status_code == 409
    assert client.post(f"/api/projects/{pid}/retry", headers=user_headers).status_code == 409

    # idle in PLANNING (no active job lease) -> cancel must be rejected truthfully
    submit_requirement(client, user_headers, pid)
    client.post(f"/api/projects/{pid}/requirements/analyze", headers=user_headers)
    r = client.post(f"/api/projects/{pid}/cancel", headers=user_headers)
    assert r.status_code == 409
    assert "no active workflow job" in r.json()["error"]["message"].lower()

    # with an active job lease, cancel is accepted and flags the workflow
    from app.core.database import SessionLocal
    from app.models.project import WorkflowState

    db = SessionLocal()
    try:
        wf = db.query(WorkflowState).filter(WorkflowState.project_id == pid).first()
        wf.job_id = "plan-testlease"
        db.commit()
    finally:
        db.close()
    r = client.post(f"/api/projects/{pid}/cancel", headers=user_headers)
    assert r.status_code == 200
    db = SessionLocal()
    try:
        wf = db.query(WorkflowState).filter(WorkflowState.project_id == pid).first()
        assert wf.cancel_requested is True
    finally:
        db.close()
