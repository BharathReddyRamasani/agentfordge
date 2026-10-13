"""Prototype readiness gate + lifecycle regression tests (scenarios C-J).

C: approval during generation / failed validation / stale version rejected.
D: rendering failure reported, never marked ready.
E: empty data shows zeros + meaningful empty states.
F: agent failure → bounded retries + accurate failed task record.
G: revision never overwrites previous versions; approval pins the right version.
H: state persists across sessions (restart-safe).
I: cross-user isolation on approve/download.
J: OpenAPI contract contains the Manus frontend endpoints.
"""

from tests.conftest import HOSPITAL_REQUIREMENT, submit_requirement


def _drive_to_review(client, headers, pid):
    submit_requirement(client, headers, pid)
    assert client.post(f"/api/projects/{pid}/requirements/analyze", headers=headers).status_code == 202
    assert client.post(f"/api/projects/{pid}/planning", headers=headers).status_code == 202
    assert client.post(f"/api/projects/{pid}/prototype/generate", headers=headers).status_code == 202
    w = client.get(f"/api/projects/{pid}/workflow", headers=headers).json()
    assert w["status"] == "AWAITING_REVIEW", w


def test_c_approve_rejected_while_building(client, user_headers, project):
    from app.core.database import SessionLocal
    from app.models.project import Project, ProjectStatus

    pid = project["id"]
    submit_requirement(client, user_headers, pid)
    db = SessionLocal()
    try:
        p = db.get(Project, pid)
        p.status = ProjectStatus.PROTOTYPE_BUILDING
        db.commit()
    finally:
        db.close()
    r = client.post(f"/api/projects/{pid}/prototype/approve", json={}, headers=user_headers)
    assert r.status_code == 409


def test_c_approve_rejected_when_validation_failed(client, user_headers, project):
    pid = project["id"]
    _drive_to_review(client, user_headers, pid)
    # Simulate a rendering failure: corrupt the built file, then revalidate
    from app.services import workspace as ws

    proto = client.get(f"/api/projects/{pid}/prototype", headers=user_headers).json()
    idx = ws.prototype_version_dir(pid, proto["version"]) / "index.html"
    idx.write_text("<html><head><title>broken</title></head><body><p>oops", encoding="utf-8")
    r = client.post(f"/api/projects/{pid}/prototype/validate", headers=user_headers)
    assert r.status_code == 200
    assert r.json()["verdict"] == "fail"
    r = client.post(f"/api/projects/{pid}/prototype/approve", json={}, headers=user_headers)
    assert r.status_code == 409
    assert "validation" in r.json()["error"]["message"].lower()


def test_c_stale_version_pin_rejected_and_correct_pin_accepted(client, user_headers, project):
    pid = project["id"]
    _drive_to_review(client, user_headers, pid)
    client.post(f"/api/projects/{pid}/prototype/feedback", json={"feedback": "Add order tracking."}, headers=user_headers)
    proto = client.get(f"/api/projects/{pid}/prototype", headers=user_headers).json()
    assert proto["version"] == 2
    r = client.post(f"/api/projects/{pid}/prototype/approve", json={"prototype_version": 1}, headers=user_headers)
    assert r.status_code == 409
    assert "stale" in r.json()["error"]["message"].lower()
    r = client.post(f"/api/projects/{pid}/prototype/approve", json={"prototype_version": 2}, headers=user_headers)
    assert r.status_code == 200


def test_d_failed_validation_marks_job_failed_not_ready():
    from app.core.database import SessionLocal, reset_db
    from app.models.artifacts import Prototype
    from app.models.project import Project, ProjectStatus
    from app.orchestrator.engine import WorkflowFailedError, WorkflowRunner

    reset_db()
    db = SessionLocal()
    try:
        p = Project(owner_id=1, name="D", description="x")
        db.add(p)
        db.commit()
        proto = Prototype(project_id=p.id, version=1, plan_version=1, requirements_version=1, spec={}, path="/nonexistent/missing.html", status="validating")
        db.add(proto)
        db.commit()
        runner = WorkflowRunner()
        try:
            runner._validate_prototype(db, p, proto, 1, "prototype_v1")
            raise AssertionError("should have raised")
        except WorkflowFailedError as exc:
            assert "validation" in str(exc).lower()
        db.refresh(proto)
        assert proto.status == "needs_attention"
    finally:
        db.close()


def test_e_empty_data_renders_zeros_and_empty_states():
    from app.schemas.prototype import PrototypeSpec
    from app.services.codegen.prototype_renderer import render_prototype
    from app.services.prototype_validation import validate_prototype_html

    spec = PrototypeSpec.model_validate({
        "app_name": "Empty App",
        "tagline": "Nothing here yet",
        "theme": {"primary_color": "#4f46e5", "accent_color": "#0ea5e9", "background_color": "#f8fafc"},
        "screens": [
            {"name": "Home", "title": "Welcome", "sections": [{"type": "hero", "title": "Empty App", "subtitle": "tag"}]},
            {"name": "Dashboard", "title": "Dashboard", "sections": [
                {"type": "stats", "title": "Stats", "stats": [{"label": "Widgets", "value": "0"}]},
                {"type": "list", "title": "All Widgets", "items": []},
            ]},
        ],
        "navigation": ["Home", "Dashboard"],
        "user_flow": ["Open the dashboard"],
        "features": ["Widgets"],
        "sample_data": {},
        "roles": [],
    })
    html = render_prototype(spec)
    open(r"D:\final\agentforge\data\empty_proto_check.html", "w", encoding="utf-8").write(html)
    report = validate_prototype_html(r"D:\final\agentforge\data\empty_proto_check.html", spec.model_dump())
    assert report.verdict == "pass", report.summary()
    assert "No records yet" in html


def test_f_agent_failure_bounded_and_recorded():
    from app.core.database import SessionLocal, reset_db
    from app.models.execution import AgentExecution, AgentTask
    from app.models.project import Project
    from app.models.user import User
    from app.agents.base import BaseAgent
    from app.agents.llm.base import BaseLLMProvider, LLMAPIError
    from app.core.security import hash_password
    from pydantic import BaseModel

    class BoomProvider(BaseLLMProvider):
        name = "boom"
        calls = 0

        def complete(self, system, user, temperature=None, max_tokens=None, timeout=None):
            type(self).calls += 1
            raise LLMAPIError("provider down", provider="boom")

    class Out(BaseModel):
        answer: str

    class TinyAgent(BaseAgent):
        name = "Tiny Agent"
        stage = "analyze"
        task = "tiny"
        output_schema = Out

        def system_prompt(self):
            return "return json"

    reset_db()
    db = SessionLocal()
    try:
        u = User(email="f@example.com", name="F", password_hash=hash_password("secret123"))
        db.add(u)
        db.commit()
        p = Project(owner_id=u.id, name="F", description="x")
        db.add(p)
        db.commit()
        agent = TinyAgent(provider=BoomProvider())
        try:
            agent.run(db, p, {"x": "y"})
            raise AssertionError("should have raised")
        except LLMAPIError:
            pass
        task = db.query(AgentTask).filter(AgentTask.project_id == p.id).one()
        assert task.status == "failed"
        assert task.attempts and task.attempts > 1
        assert task.error
        ex = db.query(AgentExecution).filter(AgentExecution.project_id == p.id).one()
        assert ex.status == "failed"
    finally:
        db.close()


def test_g_version_integrity(client, user_headers, project):
    pid = project["id"]
    _drive_to_review(client, user_headers, pid)
    from app.services import workspace as ws

    v1_bytes = (ws.prototype_version_dir(pid, 1) / "index.html").read_bytes()
    client.post(f"/api/projects/{pid}/prototype/feedback", json={"feedback": "Add order tracking."}, headers=user_headers)
    assert (ws.prototype_version_dir(pid, 1) / "index.html").read_bytes() == v1_bytes
    assert (ws.prototype_version_dir(pid, 2) / "index.html").exists()
    client.post(f"/api/projects/{pid}/prototype/approve", json={"prototype_version": 2}, headers=user_headers)
    from app.core.database import SessionLocal
    from app.models.artifacts import Approval

    db = SessionLocal()
    try:
        ap = db.query(Approval).filter(Approval.project_id == pid).one()
        assert ap.prototype_version == 2
    finally:
        db.close()


def test_h_state_persists_across_sessions(client, user_headers, project):
    pid = project["id"]
    _drive_to_review(client, user_headers, pid)
    from app.core.database import SessionLocal
    from app.models.artifacts import Feedback, Prototype
    from app.models.project import Project
    from app.models.validation import PrototypeValidation

    db = SessionLocal()
    try:
        p = db.get(Project, pid)
        assert p.status.value == "AWAITING_REVIEW"
        assert db.query(Prototype).filter(Prototype.project_id == pid).count() == 1
        assert db.query(PrototypeValidation).filter(PrototypeValidation.project_id == pid).count() >= 1
        assert db.query(Feedback).filter(Feedback.project_id == pid).count() == 0
    finally:
        db.close()


def test_i_cross_user_approval_and_download_blocked(client, user_headers, project):
    import uuid

    from tests.conftest import auth_headers_for

    pid = project["id"]
    _drive_to_review(client, user_headers, pid)
    other = auth_headers_for(client, f"evil_{uuid.uuid4().hex[:8]}@example.com")
    assert client.post(f"/api/projects/{pid}/prototype/approve", json={}, headers=other).status_code == 403
    token = other["Authorization"].split(" ", 1)[1]
    assert client.get(f"/api/projects/{pid}/download?type=full&token={token}").status_code == 403


def test_j_openapi_contract_covers_manus_endpoints(client):
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    required = [
        "/api/auth/register", "/api/auth/login", "/api/auth/logout", "/api/auth/me",
        "/api/projects", "/api/projects/{project_id}",
        "/api/projects/{project_id}/requirements",
        "/api/projects/{project_id}/requirements/analyze",
        "/api/projects/{project_id}/analysis",
        "/api/projects/{project_id}/planning",
        "/api/projects/{project_id}/plan",
        "/api/projects/{project_id}/prototype/generate",
        "/api/projects/{project_id}/prototype",
        "/api/projects/{project_id}/prototype/versions",
        "/api/projects/{project_id}/prototype/feedback",
        "/api/projects/{project_id}/prototype/approve",
        "/api/projects/{project_id}/prototype/validate",
        "/api/projects/{project_id}/prototype/preview",
        "/api/projects/{project_id}/engineering/start",
        "/api/projects/{project_id}/cancel",
        "/api/projects/{project_id}/retry",
        "/api/projects/{project_id}/workflow",
        "/api/projects/{project_id}/agents",
        "/api/projects/{project_id}/logs",
        "/api/projects/{project_id}/memory",
        "/api/projects/{project_id}/testing",
        "/api/projects/{project_id}/debugging",
        "/api/projects/{project_id}/review",
        "/api/projects/{project_id}/security",
        "/api/projects/{project_id}/artifacts",
        "/api/projects/{project_id}/documentation",
        "/api/projects/{project_id}/deployment",
        "/api/projects/{project_id}/downloads",
        "/api/projects/{project_id}/download",
        "/api/projects/{project_id}/application/preview",
        "/api/projects/{project_id}/events/stream",
        "/api/notifications",
        "/health", "/ready", "/readiness",
    ]
    missing = [p for p in required if p not in paths]
    assert not missing, f"missing from OpenAPI: {missing}"


def test_duplicate_job_guard(client, user_headers, project):
    from app.core.database import SessionLocal
    from app.models.project import WorkflowState

    pid = project["id"]
    submit_requirement(client, user_headers, pid)
    db = SessionLocal()
    try:
        wf = db.query(WorkflowState).filter(WorkflowState.project_id == pid).first()
        wf.stage_states = {"analyze": "running"}
        db.commit()
    finally:
        db.close()
    r = client.post(f"/api/projects/{pid}/requirements/analyze", headers=user_headers)
    assert r.status_code == 409
    assert "already running" in r.json()["error"]["message"]
