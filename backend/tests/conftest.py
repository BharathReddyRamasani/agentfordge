"""Test bootstrap: isolated environment (temp sqlite DB, fakeredis, mock LLM,
synchronous worker, temp workspace/RAG dirs). Environment MUST be set before any app import."""

import os
import sys
import tempfile
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="agentforge_test_"))

os.environ["DATABASE_URL"] = f"sqlite:///{(TMP / 'test.db').as_posix()}"
os.environ["REDIS_URL"] = "fakeredis://"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["WORKER_MODE"] = "sync"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["APP_ENV"] = "test"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["WORKSPACE_DIR"] = str(TMP / "workspace")
os.environ["RAG_DIR"] = str(TMP / "rag")
os.environ["SANDBOX_TIMEOUT"] = "180"
os.environ["MAX_DEBUG_ITERATIONS"] = "2"

sys.path.insert(0, str(BACKEND_DIR))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import reset_db  # noqa: E402
from app.main import app  # noqa: E402

HOSPITAL_REQUIREMENT = (
    "Build a Hospital Management System where patients can register, doctors can manage "
    "appointments, administrators can manage users, and users can view medical records."
)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db():
    reset_db()
    yield


@pytest.fixture()
def user_headers(client):
    email = f"u_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/api/auth/register",
        json={"email": email, "name": "Test User", "password": "testpass123"},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def project(client, user_headers):
    r = client.post(
        "/api/projects",
        json={"name": "Hospital Management System", "description": HOSPITAL_REQUIREMENT},
        headers=user_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def submit_requirement(client, headers, project_id, text=HOSPITAL_REQUIREMENT):
    r = client.post(f"/api/projects/{project_id}/requirements", json={"description": text}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def auth_headers_for(client, email: str, name: str = "Other User"):
    r = client.post("/api/auth/register", json={"email": email, "name": name, "password": "testpass123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
