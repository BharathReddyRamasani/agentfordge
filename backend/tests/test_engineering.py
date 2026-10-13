"""End-to-end engineering test: approve → autonomous engineering → COMPLETED.
Runs inline (sync worker, mock LLM) with REAL generated-code test execution."""

from tests.conftest import submit_requirement


def _drive_to_approval(client, headers, pid):
    submit_requirement(client, headers, pid)
    assert client.post(f"/api/projects/{pid}/requirements/analyze", headers=headers).status_code == 202
    assert client.post(f"/api/projects/{pid}/planning", headers=headers).status_code == 202
    assert client.post(f"/api/projects/{pid}/prototype/generate", headers=headers).status_code == 202
    assert client.post(f"/api/projects/{pid}/prototype/approve", json={"comment": "ok"}, headers=headers).status_code == 200


def test_engineering_pipeline_to_completed(client, user_headers, project):
    pid = project["id"]
    _drive_to_approval(client, user_headers, pid)

    r = client.post(f"/api/projects/{pid}/engineering/start", headers=user_headers)
    assert r.status_code == 202, r.text

    w = client.get(f"/api/projects/{pid}/workflow", headers=user_headers).json()
    assert w["status"] == "COMPLETED", w.get("last_error")
    assert w["progress"] == 100

    # All engineering stages completed
    stages = {s["key"]: s["status"] for s in w["stages"]}
    for key in ("architecture", "database", "backend", "frontend", "integration", "testing", "review", "security", "documentation", "deployment"):
        assert stages[key] == "completed", (key, stages.get(key))

    # Real generated tests executed and passed
    tests = client.get(f"/api/projects/{pid}/testing", headers=user_headers).json()
    assert len(tests) >= 1
    last = tests[-1]
    assert last["status"] == "passed", last["output"][-2000:]
    assert last["passed"] > 0 and last["failed"] == 0

    # Review + security records persisted
    reviews = client.get(f"/api/projects/{pid}/review", headers=user_headers).json()
    assert len(reviews) >= 1 and reviews[-1]["verdict"] in ("approved", "approved_with_notes")
    security = client.get(f"/api/projects/{pid}/security", headers=user_headers).json()
    assert len(security) >= 1 and security[-1]["critical_issues"] == 0

    # Documentation + deployment artifacts exist
    docs = client.get(f"/api/projects/{pid}/documentation", headers=user_headers).json()
    assert any("README" in d["name"] for d in docs)
    deploy = client.get(f"/api/projects/{pid}/deployment", headers=user_headers).json()
    assert any("Dockerfile" in d["path"] for d in deploy)

    # Full-scale React application: sources generated AND actually built with Vite
    from app.services import workspace as ws

    app_root = ws.application_dir(pid)
    assert (app_root / "frontend" / "package.json").exists()
    assert (app_root / "frontend" / "src" / "App.tsx").exists()
    assert (app_root / "frontend" / "src" / "entities.ts").exists()
    dist_index = app_root / "frontend" / "dist" / "index.html"
    assert dist_index.exists(), "Vite production build missing"
    assert "root" in dist_index.read_text(encoding="utf-8")

    # Live full-scale application preview serves the built SPA
    r = client.get(f"/api/projects/{pid}/application/preview?token={token}")
    assert r.status_code == 200
    assert "root" in r.text

    # Download center: all packages available with real content
    downloads = client.get(f"/api/projects/{pid}/downloads", headers=user_headers).json()
    assert {d["kind"] for d in downloads} == {"prototype", "application", "docs", "deployment", "full"}
    assert all(d["size"] > 0 for d in downloads)

    token = user_headers["Authorization"].split(" ", 1)[1]
    r = client.get(f"/api/projects/{pid}/download?type=full&token={token}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert len(r.content) > 1000

    # Agent executions recorded across all 14 roles
    agents = client.get(f"/api/projects/{pid}/agents", headers=user_headers).json()
    names = {a["agent"] for a in agents}
    for expected in ("Requirement Analysis Agent", "Planning Agent", "Product/UX & Prototype Agent", "Architecture Agent", "Database Agent", "Backend Agent", "Frontend Agent", "Integration Agent", "Testing Agent", "Review/Critic Agent", "Security/Quality Agent", "Documentation Agent", "Deployment Agent"):
        assert expected in names, expected


def test_generated_backend_actually_runs(client, user_headers, project):
    """Import the generated backend and exercise auth + CRUD for real (sandbox check)."""
    import importlib
    import os
    import sys
    import tempfile
    from pathlib import Path

    pid = project["id"]
    _drive_to_approval(client, user_headers, pid)
    client.post(f"/api/projects/{pid}/engineering/start", headers=user_headers)

    from app.services import workspace as ws

    backend_dir = ws.application_dir(pid) / "backend"
    assert (backend_dir / "main.py").exists()

    # Isolate the generated app: dedicated temp database (never the platform DB).
    tmp_db = Path(tempfile.mkdtemp()) / "gen_manual.db"
    prev_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db.as_posix()}"
    sys.path.insert(0, str(backend_dir))
    try:
        for mod in ("database", "models", "schemas", "security", "main"):
            sys.modules.pop(mod, None)
        import database

        database.init_db()
        gen_main = importlib.import_module("main")
        from fastapi.testclient import TestClient

        c = TestClient(gen_main.app)
        assert c.get("/health").status_code == 200
        email = "gen@example.com"
        assert c.post("/api/auth/register", json={"name": "G", "email": email, "password": "genpass123"}).status_code == 201
        token = c.post("/api/auth/login", json={"email": email, "password": "genpass123"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        created = c.post("/api/users", json={"name": "Extra", "email": "extra@example.com"}, headers=headers)
        assert created.status_code == 201, created.text
        item_id = created.json()["id"]
        assert c.get(f"/api/users/{item_id}", headers=headers).status_code == 200
    finally:
        sys.path.remove(str(backend_dir))
        for mod in ("database", "models", "schemas", "security", "main"):
            sys.modules.pop(mod, None)
        if prev_db_url is not None:
            os.environ["DATABASE_URL"] = prev_db_url
