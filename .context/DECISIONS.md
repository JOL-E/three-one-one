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

## 2026-11-08: M4 UI

36. **The API requires a session from day one** (Ninja `django_auth`, CSRF on
    writes). Until M5 builds the login screen and lockout, log in through
    `/admin/`. An unauthenticated API never exists, not even on localhost.
37. **Projects can be edited (name, description, repo link) by me and by
    Claude:** a new `update_project` service, API endpoint and MCP tool. Adds
    to #7/#32; changing a project's state stays owner-only.
38. **Visual direction: "Ticket"** (mockup direction A of three). Every idea
    reads like a filed report: hard rules, square corners, a mono face for
    metadata, one street-sign green accent. Chosen over a stock-iOS look
    (generic) and a dark dev-tool look: it ties to the name and doesn't look
    like my other apps. **Dark is the default**, whatever the phone says; a setting
    switches to light or to following the phone. My native-feel checklist
    applies as is.
39. **Drag-to-sort with `motion`'s Reorder**, no new dependency. Sorting is
    within one short list, with a drag handle so it doesn't fight scrolling
    on iPhone. Keyboard alternative: "Move to top / up / down" in the item
    menu. dnd-kit rejected: `core` is quiet since 2024, `react` is pre-1.0.
40. **Short item IDs, git-style** (`#3F9A`): the shortest unique start of the
    item's UUID, at least 4 characters. Computed, never stored. The tools
    accept any unique start; one matching several items is refused, naming
    them. A per-item number (`#142`) was rejected: a second ID to store, and
    offline capture couldn't know the next number. 4 characters alone would
    collide within a few hundred items, hence "grow when needed".
41. **General keeps its name** (its description can change). The MCP
    instructions tell Claude what "General" is by name.
42. **Frontend:** Vite, React 19, strict TypeScript, TanStack
    Query, React Router, React Aria Components, `motion`, Tailwind v4,
    vite-plugin-pwa; the TypeScript types are generated from Ninja's OpenAPI
    schema, and a pre-commit hook fails when they drift from the backend.
    Fonts self-hosted (@fontsource) so the shell works offline. Proven on the
    iPhone already; what differs is the look, not the plumbing.
43. **One set of URLs for both layouts:** `/inbox/:itemId?`,
    `/p/:projectId/:itemId?`, `/search/:itemId?`. With an item, the phone
    shows it full screen and the desktop beside the list. Links and the back
    button work the same everywhere.
44. **The app makes a new item's id** (`crypto.randomUUID`) and sends it, so
    a captured idea shows, and opens, before the server answers. Builds on
    #10; Claude's `add_item` doesn't take an id.
45. **The theme is a per-device setting** (browser storage), not stored on
    the server: a phone and a Mac may want different ones, and it needs no
    login to apply before the first paint.

## 2026-11-08: M5 auth

46. **OAuth server: django-oauth-toolkit (DOT) 3.4**, as #11 planned, over the
    MCP SDK's built-in authorization server. DOT 3.4 brings automatic
    registration, Client ID Metadata Documents (CIMD, with a fetcher that
    refuses internal addresses), both `.well-known` documents, resource
    indicators and any-port `localhost` redirects; the SDK has no CIMD, and
    storage, cleanup and admin would be ours to write. claude.ai now prefers
    CIMD and Claude Code uses only CIMD, so that part matters. Cost: about ten
    new packages, and Django 6.1 support is merged but not released (3.4.1
    passed checks, migrations and a registration on 6.1.3). The SDK still
    guards `/mcp` with its bearer check; a small verifier looks tokens up in DOT.
47. **Login and consent are server-rendered Django pages** in the Ticket look,
    not React screens. Django's LoginView handles safe redirects, the lockout
    plugs straight in, and OAuth's `/authorize` redirects there anyway. The
    app has no login API; its gate links to `/login/`. Seen rarely (long
    sessions), so native feel matters less than a small attack surface.
48. **Lockout: django-axes, IP + username together**, 5 failures → that pair
    is locked for 15 minutes. Locking by username alone would let anyone lock
    me out. Behind a proxy or tunnel every request comes from the proxy, so a
    `CLIENT_IP_HEADER` setting names the header with the real address
    (`CF-Connecting-IP` behind Cloudflare Tunnel). It's trusted only because
    the app can't be reached except through that proxy.
49. **Client registration is open, with limits.** Any MCP client may register
    or use CIMD from any host: registering grants nothing, every connection
    still needs my login and an "Allow". Registration is rate-limited, and
    clients that never got a token are deleted after a day.

50. **OAuth details.** One scope, `mcp`. Access tokens last 1 hour; refresh
    tokens rotate, expire after 90 days unused, and a replayed one revokes its
    successors (RFC 9700 reuse detection). Tokens stored hashed. "Allow" is
    asked every time. Only the code flow with PKCE (S256): registration and the
    token endpoint refuse other grant types, so no token exists without a
    person. Plain-http redirects only to loopback. A token without a `resource`
    counts as unrestricted (DOT's rule; some clients don't send one).
51. **Connected apps live in the Settings sheet**, with the MCP address to copy.
    Shown: name, host, "last active" (when it last got a token). "Connected
    since" can't be told honestly: rotation replaces every token. Disconnecting
    deletes the tokens; a self-registered client is deleted too.

## 2026-11-08: M6 ship

52. **The app serves its own files with WhiteNoise**: Django's `/static/`
    (hashed names) and the built React app at the root, gzipped at build time.
    Hashed files are cached for good; `index.html`, `sw.js` and the manifest
    always revalidate, or updates never reach an installed PWA. A catch-all
    view answers app URLs (`/inbox/3F9A`) with `index.html`, except the
    server's own prefixes, which keep real 404s. So the image needs no web
    server and runs the same behind any proxy. Starlette's StaticFiles (no new
    dependency) rejected: no compression or cache rules without writing them.
    WhiteNoise is sync-only; under ASGI Django reads each file whole first,
    harmless at ~0.5 MB.
53. **Image and CI.** Multi-stage Dockerfile: the frontend builds on the
    build machine's own platform (same output everywhere, never emulated), uv
    installs the locked packages without staying in the image, collectstatic
    runs at build time. Runs as uid 1000, migrates on start, one uvicorn
    process. GitHub Actions runs every check on every push. On `main`, plus
    Mondays and on demand, it builds amd64 + arm64 (QEMU for arm64) and
    publishes `latest` and `sha-<commit>` to GHCR. An amd64 smoke test must pass first,
    so a broken image never becomes `latest`. The weekly build pulls fresh base
    images: security fixes arrive without a code change. Dependabot groups
    minor/patch updates per ecosystem, majors one by one.
54. **Behind Cloudflare Tunnel, the tunnel points straight at the container**,
    no nginx in between. The image already serves its files. cloudflared sends
    `X-Forwarded-Proto` and `CF-Connecting-IP` itself, while an extra proxy has to
    forward both by hand and buffers the streamed `/mcp` request unless told
    otherwise. It's also exactly what a self-hoster with a tunnel runs.
    **Updates are a manual command** (backup, keep the old image for a
    rollback, check the new image's settings, restart, wait for healthy), not
    an auto-updater: nothing changes while nobody is watching.
55. **HTTPS follows from `BASE_URL`.** An `https` BASE_URL turns on secure
    cookies, HSTS for one year (this host only: the parent domain isn't the
    app's to decide), and trust in `X-Forwarded-Proto`. `CSRF_TRUSTED_ORIGINS`
    is BASE_URL, so the login and "Allow" forms work even if a proxy doesn't
    say "https". `ALLOWED_HOSTS` and the MCP SDK's DNS-rebinding guard (421 for
    any other `Host`) come from BASE_URL too; `ALLOWED_HOSTS` in the
    environment only adds names. One fewer setting to get wrong. uvicorn's own
    proxy-header handling is off: what the proxy may claim is decided in
    Django's settings only, next to `CLIENT_IP_HEADER`.
56. **Backups: `manage.py backup`**, SQLite's backup API (a consistent copy
    while the app writes; a file copy can be torn), integrity-checked, newest
    7 kept in `BACKUP_DIR`. The host schedules it and ships copies off-site;
    the image has no scheduler (one process). Plain `.sqlite3` files: restore
    is a copy.

## 2026-11-09: First deploy

57. **CIMD documents: grant types we don't offer are ignored.** claude.ai's
    document lists `authorization_code` and `jwt-bearer`; DOT 3.4.1 keeps one
    grant type per client and refused it ("Invalid client_id"). Claude Code's
    lists one, so only claude.ai failed, and only on the first real deploy:
    claude.ai can't reach a dev machine. A small subclass of DOT's safe fetcher
    (`CIMD_METADATA_FETCHER`) drops what the server doesn't offer before DOT
    validates; RFC 7591 allows that, and a document with no code flow left is
    still refused. Over turning CIMD off (Claude Code only does CIMD) or
    waiting for DOT. Delete it once DOT handles such documents.

## 2026-11-10: Dependencies

58. **TypeScript stays on 5.9** until openapi-typescript supports 7.
    openapi-typescript generates `schema.d.ts` with TypeScript's JavaScript
    API (`ts.factory`), which TypeScript 7 (the Go compiler) doesn't ship, so
    `gen:types` crashes; its peer range (`^5.x`) also rules out 6. npm can't
    give it its own TypeScript 5 (a peer dependency is the project's copy).
    Dependabot ignores `typescript` >= 6 until then.

## 2026-11-10: Reordering from clients that can't ask

59. **A client that can't ask gets the reorder applied unconfirmed** (narrows
    #33). The Claude mobile app speaks 2026-07-28 but doesn't declare form
    elicitation, so it couldn't reorder at all (-32021). Clients on older
    revisions never could: asking them needs a server-to-client request, which
    stateless HTTP (#20) can't send. Now the confirmation is skipped for both,
    and the result tells Claude the order was unconfirmed. Clients that can ask
    still must. Nothing is logged in the items' activity: an order is easy to
    see and to drag back. Over a separate `move_item`-style tool (another tool
    in every conversation) and over "drag it in the app" (keeps the rule, but
    the phone chat can't reprioritize).
60. **The reorder question names only the moves, on one line.** claude.ai
    drops its line breaks and Claude Code shows only its first lines, so the
    full new order hid the change. It lists the fewest moves (items outside a
    longest increasing subsequence), at most 3 plus "and N more", titles cut
    to 40 characters.

## 2026-11-10: Going public: the history

61. **The history was rewritten before going public** (`git filter-repo`):
    the pre-commit guard only ever saw file contents, so the commit metadata
    held a personal email address, and some files named private repos.
62. **Commits are authored as the GitHub handle with its noreply address**,
    not a real name. The guard now also checks the commit author and the
    commit message against the denylist.
63. **No names of the owner's other projects**, in files or history: they say
    nothing to readers and point at private repos. Replaced with neutral
    wording ("my other apps").
64. **A fresh repository instead of flipping this one public.** GitHub keeps a
    read-only copy of every pull request's branch, which still holds the old
    commits after a force-push; only GitHub Support can remove them. The old
    repository is renamed and stays private. The image name doesn't change.

## Open

- Copyright holder in `LICENSE`: currently the GitHub handle.
- Whether to-dos from my other projects move into 311 once it works: yes for
  311 itself and the first of the others (2026-11-09); the rest one by one.
- Can items be added to or moved into an Archived project? Allowed for now.
