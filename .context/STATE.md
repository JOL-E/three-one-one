# State

_Where we are. Update at the end of every session._

**Last updated:** 2026-11-08

## Now

M3 done (DECISIONS 31–35): ten MCP tools on the M2 services, plain-text
results, server `instructions`, search on `list_items`, `reorder_items`
confirmed via elicitation. Tested with Claude Code: capture, sort, comment,
status change, refused delete, and the reorder confirmation all work.
57 tests.

## Next

M4: the React PWA. Start with the decisions it needs (visual direction is
still open in DECISIONS) before any code.

## Open loops

- `.private-denylist` is filled locally. The M0 commit still names another
  project in DECISIONS "Open": clean up history in M7.
- M6: the SDK rejects any `Host` that isn't localhost (DNS-rebinding guard,
  HTTP 421). Configure it from `BASE_URL`.
- M5: the SDK has its own OAuth server/verifier support. Compare with
  django-oauth-toolkit before building.
