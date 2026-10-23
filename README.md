# Sitrep

A small, self-hosted web app for weekly project status reports.

Each week, every project gets a card with two panes: team members type a few
bullet points on the left, click **Generate executive summary**, and an executive
summary appears on the right. A badge on each card shows who updated it and
when, or that nobody has yet. Arrows in the header step back through previous
weeks. That's the whole app.

```
┌──────────────────────────────────────────────────────────────────────┐
│ Sitrep        ←  Oct 19–25, 2026  current  →     This week · Projects · Fran │
├──────────────────────────────────────────────────────────────────────┤
│ ████████░░░░  1 of 2 projects have reported this week                 │
│                                                                      │
│ ▌ Project A           ● Updated Oct 23 14:02 UTC by fran@…           │
│ ▌ WEEKLY REPORT                     EXECUTIVE SUMMARY                │
│ ▌ - shipped login page              Project A — week of 2026-10-19   │
│ ▌ - blocked on db migration         • Shipped the login page         │
│ ▌ - next: load test                 • Blocked on DB migration …      │
│ ▌                  ✦ Generate executive summary                                │
│                                                                      │
│ ▌ Project B           ● Not updated yet                              │
│ ▌ …                                                                  │
└──────────────────────────────────────────────────────────────────────┘
```

## Goals

- **Fast for the people writing reports.** Open the page, type bullets, done.
  Text auto-saves as you type.
- **Readable for leadership.** One page per week, every project, polished
  summaries, and it's obvious who hasn't reported.
- **Easy to run and maintain.** One Python process, one SQLite file, no build
  step, no JavaScript framework.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) | Small, typed, async-ready; the LLM SDKs are Python-first |
| Templates | Jinja2 | Server-rendered HTML, nothing to compile |
| Interactivity | [HTMX](https://htmx.org/) (vendored, 50 KB) | Auto-save and summary generation swap fragments without a page reload |
| Database | SQLite via SQLAlchemy | A few rows per week; swap `DATABASE_URL` for Postgres if that ever changes |
| Auth | Built-in users (bcrypt) and/or OpenID Connect via Authlib | Works standalone, or with Keycloak / any OIDC provider |
| Styling | ~200 lines of hand-written CSS, light/dark toggle | No Tailwind, no component library |

## Quick start (local)

Needs Python 3.11 or newer (the container uses 3.12).

```sh
git clone https://github.com/franchyze923/weekly-sitrep.git && cd weekly-sitrep
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run-dev.sh
```

Open <http://localhost:8000>. The first run copies `.env.example` to `.env`,
which starts the app in **dev mode**: no login page, every request is a fake
user, and two seed projects are created. Edit `.env` to change any of that.

## How it works

### Weeks

A week is identified by its Monday, as `YYYY-MM-DD` in the URL
(`/week/2026-10-19`). `/` redirects to the current week, where "current" is
judged in `APP_TZ`, so a Sunday evening in New York is still last week even
though it is already Monday in UTC. Any date in a URL
snaps to its Monday. Past weeks stay editable but show a banner.

### Projects

Managed at `/projects`: add, rename, archive, restore. Renaming changes the
display name only; the internal slug (used in URLs and the database) never
changes, so history stays attached. Archived projects disappear from the
weekly page but keep their reports.

### Reports

One row per project per week (`reports` table, unique on `project_id +
week_start`). Holds the raw bullet points, the generated summary, who last
edited it and when. Auto-save fires 1.5 s after you stop typing. The progress
bar and status badges update live after any save.

### Summaries

`app/summarize.py` is the single function that turns raw text into a summary.
**It is currently a placeholder** that tidies bullets and tags the output.
Replace its body with the LLM call when ready; the signature
`summarize(project_name, week_start, raw_text) -> str` is the only contract
the rest of the app relies on.

## Configuration

Everything is an environment variable. `run-dev.sh` loads them from `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `AUTH_MODE` | `dev` | `dev` = fake user, no login. `login` = real login page. |
| `DEV_USER_EMAIL`, `DEV_USER_NAME` | `dev@example.com`, `Dev User` | Identity used in dev mode |
| `SESSION_SECRET` | *(must set in login mode)* | Signs the session cookie. `openssl rand -hex 32` |
| `SESSION_SECURE` | `true` | Marks the cookie https-only. Set `false` **only** for local login testing over http. |
| `OIDC_DISCOVERY_URL` | *(unset)* | OIDC provider's `.well-known/openid-configuration`. Setting the three `OIDC_*` vars adds a "Log in with …" button. |
| `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` | *(unset)* | OIDC client credentials |
| `OIDC_PROVIDER_NAME` | `Keycloak` | Label on the login button |
| `APP_TZ` | `UTC` | IANA timezone for "which week is it" and displayed times, e.g. `America/New_York`. Storage is always UTC. |
| `DATABASE_URL` | `sqlite:///./data/sitrep.db` | SQLAlchemy URL. The container image defaults to `sqlite:////data/sitrep.db`. |
| `SEED_PROJECTS` | `Project A,Project B` | Created on first start if there are no projects |
| `FAKE_TODAY` | *(unset)* | Dev mode only. Pretend today is this `YYYY-MM-DD` to test week rollover. |

Safety rails: the app refuses to start with `AUTH_MODE=dev` or
`SESSION_SECURE=false` when it detects it is inside Kubernetes, and refuses
`AUTH_MODE=login` without a real `SESSION_SECRET`.

## Authentication

`AUTH_MODE=login` shows a sign-in page with up to two options:

**Built-in users.** Stored in the `users` table with bcrypt hashes. Managed
from the command line (in the cluster, prefix with
`kubectl -n weekly-sitrep exec deploy/weekly-sitrep --`):

```sh
python -m app.users add alice@example.com --name "Alice"   # prompts for a password
python -m app.users passwd alice@example.com
python -m app.users list
python -m app.users disable alice@example.com              # or enable
```

**OpenID Connect.** If `OIDC_*` is set, a "Log in with Keycloak" button runs
the standard authorization-code flow. The app never sees a password; it
receives the user's email and name from the provider and stores them in the
session cookie. The provider needs a confidential client with redirect URI
`https://<host>/auth/callback` (and `http://localhost:8000/auth/callback` if
you want to test it locally).

Either way, identity is `{email, name, via}` in a signed, http-only cookie.
Anyone who can sign in can edit any project. There is no per-project
permission model yet; add one by checking `user["email"]` or OIDC groups in
the save/generate routes.

## Testing

```sh
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q tests
```

Dependencies are pinned in `requirements.txt`; `pip-audit -r requirements.txt`
checks them against known advisories, and Dependabot opens a weekly PR for
updates. The suite spins up the app against a throwaway SQLite file per test and
covers week navigation and rollover (current/past/future, Monday snapping,
new week starts blank, weeks and projects isolated from each other), save
and generate fragments, archive and rename keeping history, the login flow,
and the startup safety rails. Runs in a few seconds; run it before a deploy.

To eyeball week rollover by hand, set `FAKE_TODAY` in `.env` (dev mode),
restart, and the app behaves as if it were that date: `/` lands on that
week, earlier weeks show the "past week" banner, and anything you typed under
the real date is still there when you unset it.

## Deploying

### Container

```sh
podman build --build-arg APP_BUILD=$(git rev-parse --short HEAD) -t franchyze923/weekly-sitrep:latest .
podman compose up            # local test of the image; uses .env and ./data
```

The release number lives in `app/__init__.py` (`__version__`); bump it when
you cut a release. The build arg stamps the git commit next to it, and both
show in the page footer and in `GET /healthz`.

The image runs as a non-root user, stores the database at `/data`, listens on
8000, and exposes `GET /healthz`. Uvicorn is started with `--proxy-headers`
so the OIDC redirect URI is built correctly behind a TLS-terminating proxy.

### Kubernetes

`k8s/weekly-sitrep.yaml` is a complete example: namespace, 1 Gi PVC,
single-replica Deployment (`Recreate` strategy, because SQLite), Service, and
a Gateway API `HTTPRoute`. Adapt the hostname and image. Create the secret
out-of-band, never in git:

```sh
kubectl -n weekly-sitrep create secret generic weekly-sitrep-oidc \
  --from-literal=SESSION_SECRET="$(openssl rand -hex 32)" \
  --from-literal=OIDC_CLIENT_SECRET="<from your OIDC provider>"
```

Then add the first user with `kubectl exec` as shown above, or sign in with
OIDC.

## Repository layout

```
app/main.py           routes and the login-required middleware
app/auth.py           dev / built-in / OIDC identity, login and callback routes
app/users.py          CLI for built-in users
app/db.py             SQLAlchemy models: projects, reports, users
app/weeks.py          Monday-of-week helpers
app/summarize.py      PLACEHOLDER for the LLM call
app/config.py         env vars and startup validation
app/templates/        base, week, projects, login, plus three HTMX fragments
app/static/htmx.min.js
Dockerfile, compose.yaml, run-dev.sh, k8s/, .env.example
```

## Roadmap

- Wire `summarize()` to an LLM, streaming the result into the summary pane
- Live refresh when a teammate saves, so the page updates without reloading
- "Copy all summaries" button for pasting into email or chat
- Keyboard shortcuts (arrows for weeks, Cmd+Enter to generate)
- Optional per-project permissions from OIDC groups
