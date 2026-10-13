"""Regression tests for the user-reported live symptoms.

S1: project stuck at 94% (DEPLOYMENT) — node_modules zipped into multi-GB archives.
S2: Request Changes completing with no visible work on stylistic feedback.
S3: Cancel reporting success when nothing is running / stale-retry recovery.
"""

from tests.conftest import submit_requirement


def test_s1_zip_excludes_node_modules_and_stays_small():
    from app.services import packaging, workspace

    pid = 424242
    root = workspace.project_root(pid)
    (root / "application" / "frontend").mkdir(parents=True, exist_ok=True)
    (root / "application" / "frontend" / "node_modules" / "some-pkg").mkdir(parents=True, exist_ok=True)
    (root / "application" / "frontend" / "node_modules" / "some-pkg" / "index.js").write_text("x" * 100000, encoding="utf-8")
    (root / "application" / "frontend" / "dist").mkdir(parents=True, exist_ok=True)
    (root / "application" / "frontend" / "dist" / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (root / "application" / "frontend" / "src").mkdir(parents=True, exist_ok=True)
    (root / "application" / "frontend" / "src" / "App.tsx").write_text("export default 1", encoding="utf-8")
    (root / "application" / "frontend" / "app.js").write_text("legacy", encoding="utf-8")

    for kind in ("application", "full"):
        path = packaging.build_zip(pid, kind)
        import zipfile

        names = zipfile.ZipFile(path).namelist()
        assert not any("node_modules" in n for n in names), names[:5]
        assert not any(n.endswith("frontend/app.js") for n in names)
        assert any(n.endswith("dist/index.html") for n in names), names[:8]
    assert path.stat().st_size < 1_000_000


def test_s2_style_feedback_produces_visible_change(client, user_headers, project):
    pid = project["id"]
    submit_requirement(client, user_headers, pid)
    client.post(f"/api/projects/{pid}/requirements/analyze", headers=user_headers)
    client.post(f"/api/projects/{pid}/planning", headers=user_headers)
    client.post(f"/api/projects/{pid}/prototype/generate", headers=user_headers)
    v1 = client.get(f"/api/projects/{pid}/prototype", headers=user_headers).json()
    assert v1["spec"]["theme"]["primary_color"] == "#4f46e5"

    r = client.post(
        f"/api/projects/{pid}/prototype/feedback",
        json={"feedback": "Change the home page to be stylish, use animations and transitions, make it modern and vibrant."},
        headers=user_headers,
    )
    assert r.status_code == 202
    v2 = client.get(f"/api/projects/{pid}/prototype", headers=user_headers).json()
    assert v2["version"] == 2
    assert v2["spec"]["theme"]["primary_color"] != "#4f46e5"
    plan = client.get(f"/api/projects/{pid}/plan", headers=user_headers).json()["plan"]
    assert "design directives" in plan.get("revision_notes", "").lower()
    # The revised, re-themed prototype still validates and is approvable
    assert v2["validation"]["verdict"] == "pass"
    assert client.post(f"/api/projects/{pid}/prototype/approve", json={"prototype_version": 2}, headers=user_headers).status_code == 200


def test_s3_stale_deployment_resumes_to_completed(client, user_headers, project):
    """Full resume execution: an interrupted DEPLOYMENT run restarts the pipeline
    (approval provenance intact) and reaches COMPLETED with sane archives."""
    from app.core.database import SessionLocal
    from app.models.project import Project, ProjectStatus

    pid = project["id"]
    submit_requirement(client, user_headers, pid)
    client.post(f"/api/projects/{pid}/requirements/analyze", headers=user_headers)
    client.post(f"/api/projects/{pid}/planning", headers=user_headers)
    client.post(f"/api/projects/{pid}/prototype/generate", headers=user_headers)
    assert client.post(f"/api/projects/{pid}/prototype/approve", json={}, headers=user_headers).status_code == 200
    # Simulate an interrupted engineering run stuck at 94% with no active job lease
    db = SessionLocal()
    try:
        p = db.get(Project, pid)
        p.status = ProjectStatus.DEPLOYMENT
        p.progress = 94
        db.commit()
    finally:
        db.close()

    r = client.post(f"/api/projects/{pid}/retry", headers=user_headers)
    assert r.status_code == 202, r.text
    w = client.get(f"/api/projects/{pid}/workflow", headers=user_headers).json()
    assert w["status"] == "COMPLETED", w.get("last_error")
    assert w["progress"] == 100

    import zipfile

    from app.services import packaging, workspace

    full = workspace.artifacts_dir(pid) / packaging.PACKAGE_NAMES["full"]
    assert full.exists()
    names = zipfile.ZipFile(full).namelist()
    assert not any("node_modules" in n for n in names)
    assert full.stat().st_size < 50_000_000, full.stat().st_size


def test_debugging_pending_without_failures_is_correct(client, user_headers, project):
    """The Debugging agent shows 'pending' when tests pass first try — that is the
    truthful state (it runs only on failure), not a stuck job."""
    pid = project["id"]
    submit_requirement(client, user_headers, pid)
    client.post(f"/api/projects/{pid}/requirements/analyze", headers=user_headers)
    agents = client.get(f"/api/projects/{pid}/agents", headers=user_headers).json()
    assert not [a for a in agents if a["agent"] == "Debugging Agent" and a["status"] == "running"]
