from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from . import auth, config, db, summarize, weeks

config.validate()
db.init_db()

BASE = Path(__file__).parent
app = FastAPI(title="Weekly Sitrep")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
app.include_router(auth.router)

templates = Jinja2Templates(directory=BASE / "templates")
templates.env.globals["week_label"] = weeks.week_label
templates.env.filters["localtime"] = weeks.localtime
templates.env.globals["app_version"] = config.APP_VERSION
templates.env.globals["app_build"] = config.APP_BUILD


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if path.startswith("/auth/") or path.startswith("/static/") or path in ("/healthz", "/favicon.ico"):
        return await call_next(request)
    if auth.current_user(request) is None:
        # Remember where to return after login, but only for real page views:
        # a browser's favicon probe or an HTMX fragment post must not become
        # the post-login destination.
        if request.method == "GET" and "hx-request" not in request.headers and not path.startswith("/favicon"):
            request.session["next"] = str(request.url.path)
        return RedirectResponse("/auth/login", status_code=303)
    return await call_next(request)


# Added after require_login so it wraps it: middleware added last runs first,
# and the login guard needs request.session to exist.
app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET,
                   https_only=config.AUTH_MODE == "login" and config.SESSION_SECURE)


def week_progress(s: Session, monday):
    projects = db.active_projects(s)
    updated = sum(1 for p in projects if (r := db.get_report(s, p, monday)) and r.raw_text.strip())
    return {"updated": updated, "total": len(projects)}


def render(request: Request, name: str, **ctx):
    ctx.update(request=request, user=auth.current_user(request), auth_mode=config.AUTH_MODE)
    return templates.TemplateResponse(request, name, ctx)


def week_or_404(text: str):
    try:
        return weeks.parse_week(text)
    except ValueError:
        raise HTTPException(404, "Bad week")


def project_or_404(s: Session, slug: str) -> db.Project:
    project = s.scalar(select(db.Project).where(db.Project.slug == slug))
    if project is None:
        raise HTTPException(404, "No such project")
    return project


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse("/static/favicon.svg")


@app.get("/healthz")
def healthz():
    return {"ok": True, "version": config.APP_VERSION, "build": config.APP_BUILD}


@app.get("/")
def home():
    return RedirectResponse("/week/{}".format(weeks.current_week().isoformat()))


@app.get("/week/{week}", response_class=HTMLResponse)
def week_page(request: Request, week: str, s: Session = Depends(db.get_session)):
    monday = week_or_404(week)
    projects = db.active_projects(s)
    rows = [(p, db.get_report(s, p, monday)) for p in projects]
    updated = sum(1 for _, r in rows if r and r.raw_text.strip())
    today = weeks.current_week()
    return render(request, "week.html",
                  monday=monday, rows=rows, updated=updated,
                  prev_week=(monday - timedelta(days=7)).isoformat(),
                  next_week=(monday + timedelta(days=7)).isoformat() if monday < today else None,
                  is_current=monday == today, is_future=monday > today)


@app.post("/week/{week}/{slug}/save", response_class=HTMLResponse)
def save_report(request: Request, week: str, slug: str, raw_text: str = Form(""),
                s: Session = Depends(db.get_session)):
    monday = week_or_404(week)
    project = project_or_404(s, slug)
    report = db.get_or_create_report(s, project, monday)
    report.raw_text = raw_text
    report.updated_by = auth.current_user(request)["email"]
    report.updated_at = datetime.utcnow()
    s.commit()
    return render(request, "_save_response.html", report=report, oob=True, **week_progress(s, monday))


@app.post("/week/{week}/{slug}/generate", response_class=HTMLResponse)
def generate_summary(request: Request, week: str, slug: str, raw_text: str = Form(""),
                     s: Session = Depends(db.get_session)):
    monday = week_or_404(week)
    project = project_or_404(s, slug)
    report = db.get_or_create_report(s, project, monday)
    report.raw_text = raw_text
    report.updated_by = auth.current_user(request)["email"]
    report.updated_at = datetime.utcnow()
    report.summary_text = summarize.summarize(project.name, monday, raw_text)
    report.summary_updated_at = datetime.utcnow()
    s.commit()
    return render(request, "_summary.html", report=report, project=project, oob=True, **week_progress(s, monday))


@app.get("/projects", response_class=HTMLResponse)
def projects_page(request: Request, s: Session = Depends(db.get_session)):
    projects = list(s.scalars(select(db.Project).order_by(db.Project.active.desc(), db.Project.sort_order, db.Project.name)))
    return render(request, "projects.html", projects=projects)


@app.post("/projects")
def add_project(name: str = Form(...), s: Session = Depends(db.get_session)):
    name = name.strip()
    if name:
        slug = db.slugify(name)
        if s.scalar(select(db.Project).where(db.Project.slug == slug)) is None:
            count = len(s.scalars(select(db.Project)).all())
            s.add(db.Project(slug=slug, name=name, sort_order=count))
            s.commit()
    return RedirectResponse("/projects", status_code=303)


@app.post("/projects/{slug}/rename")
def rename_project(slug: str, name: str = Form(...), s: Session = Depends(db.get_session)):
    project = project_or_404(s, slug)
    name = name.strip()
    if name:
        project.name = name
        s.commit()
    return RedirectResponse("/projects", status_code=303)


@app.post("/projects/{slug}/toggle")
def toggle_project(slug: str, s: Session = Depends(db.get_session)):
    project = project_or_404(s, slug)
    project.active = not project.active
    s.commit()
    return RedirectResponse("/projects", status_code=303)
