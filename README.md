# Sitrep

A small self-hosted app for weekly project status reports. Each week, every
project gets a card: team members type a few bullet points on the left, click
**Generate executive summary**, and a polished summary appears on the right.
Badges show who has reported and who hasn't. Arrows in the top-left step
back through previous weeks.

Live at `https://sitrep.franpolignano.com`. Stack: FastAPI + Jinja2 + HTMX,
SQLite, Keycloak or built-in login. One Python process, no build step.

## Run it on your laptop

Needs Python 3.11 or newer and git.

```sh
git clone https://github.com/franchyze923/weekly-sitrep.git
cd weekly-sitrep
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run-dev.sh
```

Open <http://localhost:8000>. That's it.

- First run copies `.env.example` to `.env` and starts in **dev mode**: no
  login, you are a fake user, two seed projects. Edit `.env` to change it.
- Port 8000 busy? `PORT=8001 ./run-dev.sh`
- The server reloads when you edit a file. Data lives in `./data/sitrep.db`,
  separate from the cluster's database.
- After a `git pull`, re-run `.venv/bin/pip install -r requirements.txt` in
  case dependencies changed.

To test the Keycloak login locally, set these in `.env` and restart (client
secret: Keycloak → Clients → weekly-sitrep → Credentials):

```
AUTH_MODE=login
SESSION_SECRET=<any long random string>
SESSION_SECURE=false
OIDC_DISCOVERY_URL=https://keycloak.franpolignano.com/realms/homelab/.well-known/openid-configuration
OIDC_CLIENT_ID=weekly-sitrep
OIDC_CLIENT_SECRET=<from Keycloak>
```

## Run the tests

```sh
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q tests
```

Covers week navigation and rollover, save/generate, archive and rename,
login, and the startup safety rails. Set `FAKE_TODAY=2026-11-02` in `.env`
(dev mode) to eyeball week rollover by hand.

## How it works

- **Weeks** are identified by their Monday (`/week/2026-10-19`). `/` goes to
  the current week, judged in `APP_TZ`. Past weeks stay editable with a banner.
- **Projects** are managed at `/projects` via the ⋯ menu: rename, archive,
  restore. Renaming keeps history; archiving hides the project but keeps its
  reports.
- **Reports** are one row per project per week. Text auto-saves 1.5 s after
  you stop typing. Badges and the progress bar update live.
- **Summaries** come from one function, `summarize()` in `app/summarize.py`.
  **It is a placeholder** that tidies bullets. Replace its body with the LLM
  call; the signature `summarize(project_name, week_start, raw_text) -> str`
  is the only contract.
- **Copy** buttons: one inside each summary, and **Copy all summaries** at the
  top for pasting the whole week into email or chat.

## Configuration

All environment variables; `run-dev.sh` loads them from `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `AUTH_MODE` | `dev` | `dev` = fake user, no login. `login` = sign-in page. |
| `DEV_USER_EMAIL`, `DEV_USER_NAME` | `dev@example.com`, `Dev User` | Identity in dev mode |
| `SESSION_SECRET` | *(required in login mode)* | Signs the session cookie. `openssl rand -hex 32` |
| `SESSION_SECURE` | `true` | Cookie is https-only. `false` **only** for local login testing. |
| `OIDC_DISCOVERY_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` | *(unset)* | Set all three to add "Log in with Keycloak" |
| `OIDC_PROVIDER_NAME` | `Keycloak` | Label on that button |
| `APP_TZ` | `UTC` | Timezone for "which week" and displayed times, e.g. `America/New_York` |
| `DATABASE_URL` | `sqlite:///./data/sitrep.db` | SQLAlchemy URL; container default is `sqlite:////data/sitrep.db` |
| `SEED_PROJECTS` | `Project A,Project B` | Created on first start if no projects exist |
| `FAKE_TODAY` | *(unset)* | Dev mode only: pretend it is this date |

The app refuses to start with `AUTH_MODE=dev` or `SESSION_SECURE=false`
inside Kubernetes, or `AUTH_MODE=login` without a real `SESSION_SECRET`.

## Login

In `login` mode the sign-in page offers **Log in with Keycloak** (if `OIDC_*`
is set) and an email/password form for **built-in users**, managed from the
command line:

```sh
python -m app.users add alice@example.com --name "Alice"   # prompts for password
python -m app.users list
python -m app.users passwd alice@example.com
python -m app.users disable alice@example.com              # or enable
```

In the cluster, prefix with `kubectl -n weekly-sitrep exec deploy/weekly-sitrep --`.
Anyone signed in can edit any project; there are no per-project permissions yet.

## Deploy

```sh
podman build --build-arg APP_BUILD=$(git rev-parse --short HEAD) \
  -t franchyze923/weekly-sitrep:latest -t franchyze923/weekly-sitrep:<version> .
podman push franchyze923/weekly-sitrep:latest
kubectl -n weekly-sitrep rollout restart deploy/weekly-sitrep
curl https://sitrep.franpolignano.com/healthz     # {"ok":true,"version":...,"build":...}
```

Bump `__version__` in `app/__init__.py` when cutting a release. Manifests
live in the homelab gitops repo (`gitops/workloads/weekly-sitrep`); a copy is
in `k8s/` here. The secret `weekly-sitrep-oidc` (`SESSION_SECRET`,
`OIDC_CLIENT_SECRET`) is created by hand, never committed. Dependencies are
pinned; `pip-audit -r requirements.txt` checks them and Dependabot opens a
weekly PR.

## Layout

```
app/main.py           routes + login-required middleware
app/auth.py           dev / built-in / OIDC identity
app/users.py          CLI for built-in users
app/db.py             models: projects, reports, users
app/weeks.py          Monday-of-week + timezone helpers
app/summarize.py      PLACEHOLDER for the LLM call
app/config.py         env vars + startup validation
app/templates/        base, week, projects, login, HTMX fragments
app/static/           htmx, favicon
tests/                pytest suite
k8s/                  example manifests
```

## Roadmap

- Wire `summarize()` to an LLM, streaming into the summary pane
- Live refresh when a teammate saves
- Keyboard shortcuts (arrows for weeks, Cmd+Enter to generate)
- Per-project permissions from OIDC groups
