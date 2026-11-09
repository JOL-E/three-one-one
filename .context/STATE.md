# State

_Where we are. Update at the end of every session._

**Last updated:** 2026-11-08

## Now

M5 done (DECISIONS 46–51), not committed. Login + lockout (axes), OAuth via
django-oauth-toolkit 3.4 (metadata, DCR, CIMD, consent page, bearer check on
`/mcp`), connected apps in Settings. 119 backend + 11 frontend tests. Checked
in Chrome on a scratch DB: login/logout, consent, code → token → `/mcp`,
disconnect. CIMD checked against Claude Code's real client document. All 11
tools retested over HTTP with a bearer token. Code review: 8 fixes applied.
Claude Code connected for real: login, Allow, tools, disconnect, reconnect.

## Next

M6: deploy (Docker image, HTTPS settings, Pi runbook). Then connect claude.ai.

## Open loops

- Not yet checked on a real iPhone (installed PWA, edge-swipe back, swipe rows,
  sheets). Do that once it's deployed (M6), or over the LAN before.
- Pull-to-refresh not built (lists refetch when the app comes back to the
  foreground). Bundle is 210 KB gzipped; code-split if it grows.
- `.private-denylist` is filled locally. The M0 commit still names another
  project in DECISIONS "Open": clean up history in M7.
- M6: the SDK rejects any `Host` that isn't localhost (DNS-rebinding guard,
  HTTP 421). Configure it from `BASE_URL`.
- M6: HTTPS settings (secure cookies, HSTS) from BASE_URL; `check --deploy`
  shows 4 warnings. Behind the tunnel Django sees http, so the login and
  "Allow" forms fail the CSRF origin check until `CSRF_TRUSTED_ORIGINS` (or
  `SECURE_PROXY_SSL_HEADER`) is set. DOT's Django 6.1 support isn't released yet; watch 3.5.
- If Claude gets disconnected often: refresh replay detection may be firing on
  a race; add a short `REFRESH_TOKEN_GRACE_PERIOD_SECONDS`.
- M6: serve static files in production (the login page's CSS and fonts come
  from Django's `/static/`).
