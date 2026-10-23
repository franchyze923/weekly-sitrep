import sys
import tempfile

import pytest


@pytest.fixture
def login_client(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("AUTH_MODE", "login")
    monkeypatch.setenv("SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("SESSION_SECURE", "false")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///{}/t.db".format(tmp))
    for v in ("OIDC_DISCOVERY_URL", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "FAKE_TODAY", "KUBERNETES_SERVICE_HOST"):
        monkeypatch.delenv(v, raising=False)
    for m in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        del sys.modules[m]
    from fastapi.testclient import TestClient
    from app import users
    from app.main import app
    users.main(["add", "alice@example.com", "--name", "Alice", "--password", "correct-horse"])
    with TestClient(app) as c:
        yield c


def test_anonymous_is_redirected_to_login(login_client):
    r = login_client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/auth/login"


def test_login_page_without_oidc_has_no_keycloak_button(login_client):
    html = login_client.get("/auth/login").text
    assert "Sign in" in html and "Log in with" not in html


def test_wrong_password_rejected(login_client):
    r = login_client.post("/auth/login", data={"email": "alice@example.com", "password": "nope"}, follow_redirects=False)
    assert r.headers["location"].endswith("error=bad")


def test_login_logout_cycle(login_client):
    r = login_client.post("/auth/login", data={"email": "Alice@Example.com", "password": "correct-horse"}, follow_redirects=False)
    assert r.headers["location"] == "/"
    assert "Alice" in login_client.get("/").text
    login_client.get("/auth/logout")
    assert login_client.get("/", follow_redirects=False).status_code == 303


def test_disabled_user_rejected(login_client):
    from app import users
    users.main(["disable", "alice@example.com"])
    r = login_client.post("/auth/login", data={"email": "alice@example.com", "password": "correct-horse"}, follow_redirects=False)
    assert r.headers["location"].endswith("error=bad")
