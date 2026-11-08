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
PWA (frontend), one Docker image. Structure: _(added in M1)_

## Run & test

_(added in M1)_

## Deploy

One Docker image for every installation. Not deployed yet.

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

## End of session

Update `.context/STATE.md` (and DECISIONS if something was decided), then
suggest a commit message and the commands. Don't commit.
