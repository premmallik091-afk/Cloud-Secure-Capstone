import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from app import User, create_app, db


@pytest.fixture()
def client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://",
                      "SQLALCHEMY_ENGINE_OPTIONS": {}, "SECRET_KEY": "test-secret-key-0123456789abcdef"})
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app.test_client()


def reg(c, email="a@b.com", pw="Passw0rdX", name="Alice"):
    return c.post("/api/register", json={"name": name, "email": email, "password": pw})


def token(c, email="a@b.com", pw="Passw0rdX"):
    return c.post("/api/login", json={"email": email, "password": pw}).get_json()["token"]


def auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_health(client):
    assert client.get("/api/health").get_json()["status"] == "ok"


def test_register_and_login(client):
    assert reg(client).status_code == 201
    assert client.post("/api/login", json={"email": "a@b.com", "password": "Passw0rdX"}).status_code == 200


def test_duplicate_email(client):
    reg(client)
    assert reg(client).status_code == 409


@pytest.mark.parametrize("pw", ["short1", "allletters", "12345678"])
def test_weak_passwords_rejected(client, pw):
    assert reg(client, pw=pw).status_code == 400


def test_bad_email_rejected(client):
    assert reg(client, email="nope").status_code == 400


def test_wrong_password(client):
    reg(client)
    assert client.post("/api/login", json={"email": "a@b.com", "password": "wrong"}).status_code == 401


def test_password_stored_hashed(client):
    reg(client)
    with client.application.app_context():
        h = User.query.first().password_hash
    assert "Passw0rdX" not in h and len(h) > 40


def test_protected_routes_need_token(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/notes", headers=auth("garbage")).status_code == 401


def test_notes_crud_and_isolation(client):
    reg(client)
    reg(client, email="b@b.com", name="Bob")
    ta, tb = token(client), token(client, "b@b.com")
    nid = client.post("/api/notes", json={"content": "hello"}, headers=auth(ta)).get_json()["id"]
    assert len(client.get("/api/notes", headers=auth(ta)).get_json()) == 1
    assert client.get("/api/notes", headers=auth(tb)).get_json() == []
    assert client.delete(f"/api/notes/{nid}", headers=auth(tb)).status_code == 404
    assert client.delete(f"/api/notes/{nid}", headers=auth(ta)).status_code == 200


def test_sql_injection_attempt_is_harmless(client):
    reg(client)
    r = client.post("/api/login", json={"email": "' OR '1'='1", "password": "x"})
    assert r.status_code == 401


def test_security_headers(client):
    h = client.get("/api/health").headers
    assert h["X-Content-Type-Options"] == "nosniff" and h["X-Frame-Options"] == "DENY"
