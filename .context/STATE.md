# State

_Where we are. Update at the end of every session._

**Last updated:** 2026-11-08

## Now

M4 done (DECISIONS 36–45). The PWA: quick capture, inbox with swipe actions,
projects by state, drag-to-sort (plus Top/Up/Down), move sheet, item detail
with log and comments, status changes that ask why, project create/edit/
state/delete, search, settings (theme). Dark by default, "Ticket" look
(STYLE_GUIDE). Desktop: sidebar · list · item. Backend: API at `/api/`
(session + CSRF), short item IDs everywhere, `update_project` for Claude.
83 backend + 10 frontend tests. Checked in Chrome on synthetic data: phone
and desktop layouts, move, reorder, mark done, search, light theme.

## Next

M5: auth. Login screen + lockout (replaces logging in via `/admin/`), then
OAuth for MCP clients.

## Open loops

- Not yet checked on a real iPhone (installed PWA, edge-swipe back, swipe rows,
  sheets). Do that once it's deployed (M6), or over the LAN before.
- Retest the MCP tools with Claude Code: results now carry short IDs, and
  there's an 11th tool (`update_project`).
- Pull-to-refresh not built (lists refetch when the app comes back to the
  foreground). Bundle is 210 KB gzipped; code-split if it grows.
- `.private-denylist` is filled locally. The M0 commit still names another
  project in DECISIONS "Open": clean up history in M7.
- M6: the SDK rejects any `Host` that isn't localhost (DNS-rebinding guard,
  HTTP 421). Configure it from `BASE_URL`.
- M5: the SDK has its own OAuth server/verifier support. Compare with
  django-oauth-toolkit before building.
