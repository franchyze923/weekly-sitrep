"""All configuration comes from environment variables. See .env.example."""
import os
import sys

from . import __version__


def _env(name, default=None):
    value = os.environ.get(name)
    return value if value not in (None, "") else default


# "dev": every request is the fake DEV_USER, no login page. Local hacking only.
# "login": login page with built-in users; plus "Log in with Keycloak" when OIDC_* is set.
AUTH_MODE = _env("AUTH_MODE", "dev")
DEV_USER_EMAIL = _env("DEV_USER_EMAIL", "dev@example.com")
DEV_USER_NAME = _env("DEV_USER_NAME", "Dev User")
# Dev mode only: pretend today is this date (YYYY-MM-DD) to test week rollover.
FAKE_TODAY = _env("FAKE_TODAY")

SESSION_SECRET = _env("SESSION_SECRET", "change-me-in-production")
# Session cookie marked Secure (https only). Set to "false" only for local login testing over http.
SESSION_SECURE = _env("SESSION_SECURE", "true").lower() != "false"

OIDC_DISCOVERY_URL = _env("OIDC_DISCOVERY_URL")
OIDC_CLIENT_ID = _env("OIDC_CLIENT_ID")
OIDC_CLIENT_SECRET = _env("OIDC_CLIENT_SECRET")
OIDC_PROVIDER_NAME = _env("OIDC_PROVIDER_NAME", "Keycloak")
OIDC_ENABLED = bool(OIDC_DISCOVERY_URL or OIDC_CLIENT_ID or OIDC_CLIENT_SECRET)

DATABASE_URL = _env("DATABASE_URL", "sqlite:///./data/sitrep.db")

# IANA timezone used for "what week is it" and for displaying timestamps.
# Timestamps are stored in UTC regardless.
APP_TZ = _env("APP_TZ", "UTC")

# Shown in the footer and /healthz. Release number from app/__init__.py; the
# container build appends the git commit (APP_BUILD) so a deployed pod can be
# traced back to a commit.
APP_VERSION = __version__
APP_BUILD = _env("APP_BUILD")

# Comma-separated list of projects created on first start if the table is empty.
SEED_PROJECTS = [p.strip() for p in _env("SEED_PROJECTS", "Project A,Project B").split(",") if p.strip()]


def validate():
    """Refuse unsafe combinations before the server starts serving."""
    in_kubernetes = "KUBERNETES_SERVICE_HOST" in os.environ
    try:
        import zoneinfo
        zoneinfo.ZoneInfo(APP_TZ)
    except Exception:
        sys.exit("APP_TZ={!r} is not a valid IANA timezone (e.g. America/New_York).".format(APP_TZ))
    if AUTH_MODE not in ("dev", "login"):
        sys.exit("AUTH_MODE must be 'dev' or 'login'.")
    if FAKE_TODAY and AUTH_MODE != "dev":
        sys.exit("FAKE_TODAY only works with AUTH_MODE=dev.")
    if AUTH_MODE == "dev" and in_kubernetes:
        sys.exit("AUTH_MODE=dev is not allowed inside Kubernetes. Set AUTH_MODE=login.")
    if not SESSION_SECURE and in_kubernetes:
        sys.exit("SESSION_SECURE=false is not allowed inside Kubernetes.")
    if AUTH_MODE == "login":
        if SESSION_SECRET == "change-me-in-production":
            sys.exit("Set SESSION_SECRET to a random value when AUTH_MODE=login.")
        if OIDC_ENABLED:
            missing = [n for n, v in (
                ("OIDC_DISCOVERY_URL", OIDC_DISCOVERY_URL),
                ("OIDC_CLIENT_ID", OIDC_CLIENT_ID),
                ("OIDC_CLIENT_SECRET", OIDC_CLIENT_SECRET),
            ) if not v]
            if missing:
                sys.exit("OIDC is partially configured; also set: " + ", ".join(missing))
