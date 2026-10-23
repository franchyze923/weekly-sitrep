import importlib
import sys

import pytest


def _load(monkeypatch, **env):
    for v in ("AUTH_MODE", "SESSION_SECRET", "SESSION_SECURE", "FAKE_TODAY", "KUBERNETES_SERVICE_HOST",
              "OIDC_DISCOVERY_URL", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET"):
        monkeypatch.delenv(v, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    sys.modules.pop("app.config", None)
    import app.config as config
    return importlib.reload(config)


def test_dev_mode_refused_in_kubernetes(monkeypatch):
    with pytest.raises(SystemExit):
        _load(monkeypatch, AUTH_MODE="dev", KUBERNETES_SERVICE_HOST="1").validate()


def test_login_mode_needs_session_secret(monkeypatch):
    with pytest.raises(SystemExit):
        _load(monkeypatch, AUTH_MODE="login").validate()


def test_partial_oidc_refused(monkeypatch):
    with pytest.raises(SystemExit):
        _load(monkeypatch, AUTH_MODE="login", SESSION_SECRET="s", OIDC_CLIENT_ID="x").validate()


def test_fake_today_only_in_dev(monkeypatch):
    with pytest.raises(SystemExit):
        _load(monkeypatch, AUTH_MODE="login", SESSION_SECRET="s", FAKE_TODAY="2026-01-05").validate()


def test_valid_login_config(monkeypatch):
    _load(monkeypatch, AUTH_MODE="login", SESSION_SECRET="s").validate()
