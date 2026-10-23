"""Identity.

AUTH_MODE=dev    every request is a fixed fake user; no login page.
AUTH_MODE=login  /auth/login shows a form for built-in users (table `users`,
                 bcrypt passwords, managed with `python -m app.users`) and,
                 when OIDC_* is configured, a "Log in with Keycloak" button
                 that runs the OpenID Connect authorization-code flow.
Either way the identity ends up in the signed session cookie as
{"email", "name", "via"}.
"""
import bcrypt
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config, db

router = APIRouter(prefix="/auth")
oauth = OAuth()

if config.OIDC_ENABLED:
    oauth.register(
        name="oidc",
        client_id=config.OIDC_CLIENT_ID,
        client_secret=config.OIDC_CLIENT_SECRET,
        server_metadata_url=config.OIDC_DISCOVERY_URL,
        client_kwargs={"scope": "openid profile email"},
    )


def current_user(request: Request):
    """Returns {"email", "name", "via"} or None. Used by the page routes."""
    if config.AUTH_MODE == "dev":
        return {"email": config.DEV_USER_EMAIL, "name": config.DEV_USER_NAME, "via": "dev"}
    return request.session.get("user")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def _safe_next(request: Request) -> str:
    """Post-login destination: a local path only, never an external URL."""
    nxt = request.session.pop("next", "/") or "/"
    if not nxt.startswith("/") or nxt.startswith("//") or nxt.startswith("/auth/"):
        return "/"
    return nxt


def _finish_login(request: Request, email: str, name: str, via: str):
    request.session["user"] = {"email": email, "name": name or email, "via": via}
    return RedirectResponse(_safe_next(request), status_code=303)


@router.get("/login", name="login_page")
def login_page(request: Request, error: str = ""):
    if config.AUTH_MODE == "dev" or current_user(request):
        return RedirectResponse("/")
    from .main import render  # late import: main imports this module
    return render(request, "login.html", error=error,
                  oidc_enabled=config.OIDC_ENABLED, oidc_name=config.OIDC_PROVIDER_NAME)


@router.post("/login")
def login_submit(request: Request, email: str = Form(""), password: str = Form(""),
                 s: Session = Depends(db.get_session)):
    user = s.scalar(select(db.User).where(db.User.email == email.strip().lower(), db.User.active == True))
    if user is None or not check_password(password, user.password_hash):
        return RedirectResponse("/auth/login?error=bad", status_code=303)
    return _finish_login(request, user.email, user.name, "local")


@router.get("/oidc")
async def oidc_start(request: Request):
    if not config.OIDC_ENABLED:
        return RedirectResponse("/auth/login")
    redirect_uri = request.url_for("auth_callback")
    return await oauth.oidc.authorize_redirect(request, str(redirect_uri))


@router.get("/callback", name="auth_callback")
async def callback(request: Request):
    try:
        token = await oauth.oidc.authorize_access_token(request)
    except OAuthError:
        # Stale or forged state/code: start over rather than show a stack trace.
        return RedirectResponse("/auth/login?error=oidc")
    info = token.get("userinfo") or {}
    email = info.get("email", "")
    name = info.get("name") or info.get("preferred_username") or email
    return _finish_login(request, email, name, "oidc")


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/auth/login" if config.AUTH_MODE == "login" else "/")
