# CLAUDE.md: 311

An inbox for side-project ideas: a phone-friendly app for the owner, plus an
MCP server so Claude can add, write up and update items. Self-hosted, single
user, open source (MIT) once it works.

Shared context about me, my other projects and my server lives in my private context repo.

## Mode

**Explain, then build.** I want to understand how MCP works. Before writing
code, say *why* the approach fits; explain MCP and OAuth mechanics as they come
up, with the actual requests and responses where that helps. React/TypeScript
is newer territory for me: explain unfamiliar patterns. Django I know.

- Never commit or push unless I ask. Suggest the message and commands.
- Never SSH to the Pi. Write a runbook I execute.
- Architecture and product decisions are mine: propose with a recommendation.

## Written for the public from the first commit

This repo goes public. Treat every file, commit message and issue as public now:
- No secrets: `.env` is gitignored, only `.env.example` is committed.
- None of my real data. My ideas live in my database, never in tests,
  fixtures, examples or screenshots. Synthetic data only.
- Nothing specific to my setup: no domains, hostnames or usernames in code or
  docs. Everything deployment-specific is a setting. My own Pi deployment notes
  live in my private context repo, not here.
- `scripts/check_private_data.py` (pre-commit) enforces this with a gitignored
  `.private-denylist`.

## Stack & structure

Django + Django Ninja + SQLite + MCP Python SDK (backend), React + TypeScript
PWA (frontend), one Docker image. Python deps with `uv`.

- `backend/config/`: settings (all from env vars), URLs, `asgi.py` (routes
  `/mcp` to the MCP SDK, everything else to Django)
- `backend/inbox/`: models, `services.py` (every rule lives here), `api.py`
  (the app's API at `/api/`, session + CSRF), admin
- `backend/accounts/`: login, logout, lockout (django-axes) and, from M5, the
  OAuth server (django-oauth-toolkit). Server-rendered pages, own small CSS.
- `backend/mcp_tools/`: MCP server and tools (thin), dev wire logger.
  Never name a package `mcp`: it would shadow the SDK.
- `frontend/`: React PWA. `src/api/` (generated types + TanStack Query hooks:
  every read and write), `src/screens/`, `src/components/`, `src/lib/`.
  Look and native-feel rules: `.context/STYLE_GUIDE.md`.

## Run & test

From `backend/`:
- Run: `DEBUG=1 uv run uvicorn config.asgi:application --reload` (prints every
  MCP message). Migrate first: `DEBUG=1 uv run python manage.py migrate`.
  A login: `DEBUG=1 uv run python manage.py createsuperuser`.
- Test: `uv run pytest`. Types: `uv run mypy .`. Lint: `uv run ruff check .`
- Connect Claude Code: `claude mcp add --transport http 311-dev http://localhost:8000/mcp`
- MCP SDK is v2 (`MCPServer`, not `FastMCP`); check the installed source, not v1 docs.

From `frontend/` (with the backend running on :8000):
- Run: `npm run dev` (http://localhost:5173, forwards `/api`, `/admin` and the
  server pages like `/login/`). Log in with a superuser.
- Test: `npm test`. Types: `npm run typecheck`. Lint: `npm run lint`.
- After changing the API: `npm run gen:api` (pre-commit checks it's current).

## Deploy

One Docker image for every installation (`Dockerfile`, example `compose.yaml`,
`deploy/cloudflare/`). Guide for self-hosters: `docs/self-hosting.md`.
CI (`.github/workflows/ci.yml`) checks every push and publishes the image to
GHCR from `main` and weekly. Local build: `docker build -t three-one-one .`
The runbook for my own installation lives in my private context repo, not here.

## Rules for this project

- **Tool rules are enforced by the server**, never only by tool descriptions
  (e.g. a status change without a comment is rejected).
- **Claude may not delete or change a project's state.** Those tools don't exist.
- Item IDs are generated when the item is created, not by the database
  (keeps offline capture possible later).

## Where knowledge lives

- `.context/STATE.md`: where we are, next step. ~30 lines.
- `.context/ROADMAP.md`: milestones in order, and why.
- `.context/DECISIONS.md`: every non-trivial decision, dated, with its why.
- `.context/ARCHITECTURE.md`: what the code can't say itself.
- `.context/STYLE_GUIDE.md`: the UI's look and native-feel requirements.
- To-dos and ideas: in my own 311 installation (project "311", via its MCP
  tools), not in markdown.

## End of session

Update `.context/STATE.md` (and DECISIONS if something was decided), add new
to-dos to 311 and mark finished ones done there, then suggest a commit message
and the commands. Don't commit.
