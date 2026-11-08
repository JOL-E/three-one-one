# Decisions

Dated, with the why. A change of mind is a new entry, not an edit.

## 2026-11-08: Initial design (one long design session)

**What it is.** An inbox for side-project ideas that Claude can reach. Started
from a real problem: ideas scattered across chats, sessions and the phone, with
every markdown-based list going stale. The fix is an app with a UI I actually
use, plus an MCP server so every Claude can read and write the same data.

1. **One person per installation.** Far simpler than accounts and sharing;
   typical for self-hosted tools.
2. **Dev-focused, repo link optional.** A sharp product beats a general to-do
   app competing with Todoist and co. Short-lived, date-driven things (trips)
   belong in other tools. The repo link is optional, so non-code projects fit.
3. **Projects: Idea → Building → Live → Archived** (not strictly linear; Live
   can go back to Building). "Idea" collects notes for something that might
   become a project. A permanent **General** project holds "look into / try"
   items that will never be their own project.
4. **Items: Inbox → Open → Doing → Done**, delete anytime. Inbox = no project
   yet; sorting = assigning a project.
5. **Activity log on every item**, author (me or Claude) + time + text.
   **A status change requires a comment**, enforced by the server: a rule in a
   tool description is a request, a server check is a rule.
6. **Priority = order within a project.** No global order (simplest; answers
   "what's next in X").
7. **What Claude may do:** list projects/items, read items, add items (inbox
   unless a project is given), update title/details/status (with comment), move
   items, create projects (always as Idea), reorder (marked so that clients ask
   me before every call). **Only I** delete and change a project's state.
   Claude captures and keeps things current; decisions stay with me. Few tools,
   because every tool description costs context in every conversation.
8. **Stack: Django + Django Ninja + SQLite + MCP Python SDK; React + TypeScript
   PWA.** Python because it's my strong language and learning MCP is easier in
   code I read fluently. Django for login, admin and a mature OAuth library
   (django-oauth-toolkit). React PWA because the UI must feel native
   on Mac and iPhone (instant drag-to-sort, transitions); HTMX would round-trip
   on every interaction. TypeScript backend considered (reference MCP SDK, one
   language) and rejected: small gain, loses Django's batteries.
9. **SQLite, not Postgres.** Plenty for one user; for self-hosters it's one
   file instead of a second server, and backup is a file copy.
10. **Offline capture not in v1**, but item IDs are generated at creation so it
    can be added without duplicates later.
11. **Auth.** Django login for me. OAuth 2.1 for MCP clients: the app is both
    authorization server and resource server (django-oauth-toolkit + the two
    `.well-known` metadata documents), PKCE, short access tokens + refresh.
    **Automatic client registration in v1** (other MCP clients expect it; it's
    about a page of code plus rate limit and cleanup); a pre-registered client
    only for the first test. Check at build time whether claude.ai prefers the
    newer Client ID Metadata Documents. **"Connected apps" page** with revoke.
    **Lockout of repeated failed logins** from day one: the MCP and OAuth
    endpoints must be public (claude.ai calls from Anthropic's servers), so the
    app's own login is the real lock.
12. **One Docker image for every installation, mine included.** Running what
    others run keeps the self-hosting path tested daily. Async server (uvicorn),
    one process (safe for SQLite). Frontend built in the image. Multi-arch
    builds in GitHub Actions. Public address via a `BASE_URL` setting.
13. **MIT license.** Chosen deliberately after discussing AGPL and PolyForm
    Noncommercial: simplest and most welcoming, accepting that commercial use
    is allowed.
14. **Private until it works, written as public from the first commit.** No
    secrets, no real data, nothing setup-specific; enforced by a pre-commit
    guard. Squashing history before going public is the fallback, not the plan.
15. **Name: 311**, after New York's line for reporting anything: it gets a
    number, is routed to the right place and tracked until closed. Repo and
    package `three-one-one` / `three_one_one`: searchable, and no special cases
    for a name starting with a digit.
16. **Mode: Explain, then build.** I want to understand how MCP works.

## 2026-11-08: M1 spike setup

17. **Layout: `backend/` + `frontend/`**; Django apps `config`,
    `inbox`, `mcp_tools`. Familiar, and the frontend gets its own toolchain.
18. **`uv` for Python dependencies** (Claude's call, delegated). Lockfile with
    exact versions, installs Python itself, fast; the Docker image can use it
    directly. Mainstream enough to count as boring.
19. **One ASGI app, routed by path.** `/mcp` → the MCP SDK's own app, the rest
    → Django. No django-mcp wrapper library (hides what we want to learn, one
    more dependency); not inside a Django view (the SDK needs ASGI startup
    events, which Django doesn't forward).
20. **Stateless HTTP + plain JSON responses.** Every POST stands alone, no
    session IDs, no SSE streaming. Fits one process and is readable with curl.
    Revisit only if we need server→client messages.
21. **MCP Python SDK v2** (`MCPServer`). It also answers the newer
    handshake-free protocol revision (2026-07-28) next to the older ones.

22. **Correction to #20: one request streams.** Claude Code speaks the
    handshake-free revision (2026-07-28). Its `subscriptions/listen` request
    is always an SSE stream (pings every few seconds) for "tool list changed"
    notifications, whatever the server is configured to do. Everything else
    stays plain JSON. Matters in M6: the proxy must allow long-lived responses.

## 2026-11-08: M2 data model

23. **Services are sync, one transaction per write.** Django 6.1 has no async
    `transaction.atomic`, and a status change must write the item and its log
    entry together. The async MCP tools call them through `sync_to_async`.
24. **Inbox = no project, not a status.** Status is Open / Doing / Done; an
    inbox item is always Open. Sorting into a project is a move: logged, but
    no comment needed. One fact stored once instead of two kept in sync.
25. **A project with items can't be deleted** (FK `PROTECT`). Archiving is the
    normal end; deleting is for mistakes, and it shouldn't take items with it.
26. **Activity log records: created, comment, status change, move.** Edits to
    title/details aren't logged (noise). Append-only. Status/move entries keep
    old and new value as text, as they were at the time.
27. **Order = integer `position`, renumbered by the server, gapless.** Only
    Open/Doing items in a project have one; new and reopened items go to the
    bottom. Done items sort by `done_at`, newest first; the inbox by creation,
    newest first, and can't be reordered.
28. **Project state: any to any, owner only. General is fixed:** one only,
    always Building, can't be archived or deleted. Created by a data migration.
29. **Invariants also live in the database** as check/unique constraints; the
    services check first for readable messages. No unique (project, position):
    SQLite can't defer it, so every renumbering would need two passes.
30. **M1's migration was regenerated, not extended.** It was never deployed.

## 2026-11-08: M3 tool set

31. **Tool results are plain text (compact JSON), no `outputSchema`.** The
    schema made each tool 2–3.5× bigger in `tools/list`, in every
    conversation; Claude reads the text either way and nothing else consumes it.
32. **Ten tools:** `list_projects`, `list_items`, `get_item`, `add_item`,
    `update_item`, `set_status`, `move_item`, `add_comment`, `create_project`,
    `reorder_items`. `add_comment` and `get_item` added to #7: commenting is how
    Claude keeps items current; lists stay short (titles only) and details come
    on demand. Shared concepts live once in the server `instructions`.
33. **Reordering is confirmed by the user through elicitation**, not a hint.
    The server answers the first call with `input_required` and a question;
    only an "accept" in the retry reorders. A client without elicitation can't
    reorder at all. The tool takes the whole new order (one question per
    reshuffle), checked before asking so nobody confirms an invalid list.

34. **`list_items` can search** (all words in the title, inbox and every
    project, results name their project). Tested with Claude Code: finding one
    item by name took 5 calls walking every project; with search it's one.
35. **Pydantic's generated `title` labels are stripped from `tools/list`**
    (about 13% smaller). They only repeat the property names.

## Open

- Copyright holder in `LICENSE`: currently the GitHub handle.
- Visual direction and style guide (reuse my native-feel checklist).
- Whether to-dos from my other projects move into 311 once it works.
- Can items be added to or moved into an Archived project? Allowed for now.
