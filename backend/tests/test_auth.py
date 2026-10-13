"""Authentication: registration, login, current user, and failure modes."""

import uuid


def _email():
    return f"t_{uuid.uuid4().hex[:8]}@example.com"


def test_register_login_me(client):
    email = _email()
    r = client.post("/api/auth/register", json={"email": email, "name": "Alice", "password": "secret123"})
    assert r.status_code == 201, r.text
    assert r.json()["user"]["email"] == email

    r = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == email


def test_register_duplicate_email_rejected(client):
    email = _email()
    payload = {"email": email, "name": "Bob", "password": "secret123"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_login_wrong_password_rejected(client):
    email = _email()
    client.post("/api/auth/register", json={"email": email, "name": "Bob", "password": "secret123"})
    r = client.post("/api/auth/login", json={"email": email, "password": "wrongpass1"})
    assert r.status_code == 401


def test_protected_routes_require_auth(client):
    assert client.get("/api/projects").status_code in (401, 403)
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401


def test_passwords_are_hashed(client):
    from app.core.database import SessionLocal
    from app.models.user import User

    email = _email()
    client.post("/api/auth/register", json={"email": email, "name": "Hash", "password": "secret123"})
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        assert user.password_hash != "secret123"
        assert len(user.password_hash) > 20
    finally:
        db.close()
