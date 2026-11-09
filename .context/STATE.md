# State

_Where we are. Update at the end of every session._

**Last updated:** 2026-11-08

## Now

M6 code done (DECISIONS 52–56), not committed, not deployed. Docker image
(WhiteNoise serves the app and static files), HTTPS settings and the MCP host
guard from `BASE_URL`, `manage.py backup`, CI (checks, amd64 smoke test,
amd64 + arm64 to GHCR on `main` and weekly), Dependabot. 135 backend tests.
Image built and run on the Mac with an https `BASE_URL`: app, login (with and
without `X-Forwarded-Proto`), OAuth metadata, MCP tool call with a token, 421
for a foreign `Host`, backup, the runbook's compose and deploy steps.
Pi runbook: in my private context repo (tunnel straight to the
container, no nginx).

## Next

Commit + push, wait for CI's first image, then the Pi runbook. Then connect
claude.ai and Claude Code, import `parked-for-311.md`, and check on a real
iPhone. Then M7.

## Open loops

- CI hasn't run yet: the workflow is untested until the first push.
- Not yet checked on a real iPhone (installed PWA, edge-swipe back, swipe rows,
  sheets): runbook C4.
- Pull-to-refresh not built (lists refetch when the app comes back to the
  foreground). Bundle is 210 KB gzipped; code-split if it grows.
- `.private-denylist` is filled locally. The M0 commit still names another
  project in DECISIONS "Open": clean up history in M7.
- DOT's Django 6.1 support isn't released yet (still 3.4.1); watch 3.5.
- If Claude gets disconnected often: refresh replay detection may be firing on
  a race; add a short `REFRESH_TOKEN_GRACE_PERIOD_SECONDS`.
- After deploy, add 311 to `pi.md`'s app table and `projects.md` "Runs on".
