import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client(monkeypatch):
    """Fresh app + empty SQLite DB per test, in dev mode with a fixed 'today'."""
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("DEV_USER_EMAIL", "tester@example.com")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///{}/t.db".format(tmp))
    monkeypatch.setenv("SEED_PROJECTS", "Alpha,Beta")
    monkeypatch.setenv("FAKE_TODAY", "2026-10-22")  # a Thursday; week = 2026-10-19
    monkeypatch.setenv("APP_TZ", "America/New_York")
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    for m in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        del sys.modules[m]
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
