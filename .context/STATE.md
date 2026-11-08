# State

_Where we are. Update at the end of every session._

**Last updated:** 2026-11-08

## Now

M1 spike built (DECISIONS 17–21): Django + MCP SDK v2 in one ASGI app, tools
`list_items` / `add_item` on a throwaway `Item` model, wire logger, 7 tests,
ruff + mypy strict + pytest in pre-commit. Verified with curl against uvicorn.

## Next

M2: the real data model. (M1 is complete: Claude Code connected and works,
using protocol 2026-07-28, see DECISIONS #22.)

## Open loops

- `.private-denylist` is filled locally. The M0 commit still names another
  project in DECISIONS "Open": clean up history in M7.
- M3: structured tool output roughly doubles each tool's size in `tools/list`
  (an `outputSchema` per tool). Decide plain text vs structured.
- M6: the SDK rejects any `Host` that isn't localhost (DNS-rebinding guard,
  HTTP 421). Configure it from `BASE_URL`.
- M5: the SDK has its own OAuth server/verifier support. Compare with
  django-oauth-toolkit before building.
