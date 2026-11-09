# Architecture

Only what the code can't say itself.

## Two front doors, one database

```
 Me (browser / iPhone PWA)            Claude (claude.ai, Claude Code, other MCP clients)
          │                                          │
     session login                             OAuth access token
          │                                          │
     /api/…  (Ninja)                            /mcp  (MCP SDK)
          └──────────────┬───────────────────────────┘
                   services layer   ← every rule lives here
                         │
                      SQLite
```

- **Both doors call the same services.** The UI and the MCP tools are thin; a
  rule (e.g. "status change needs a comment") is enforced once, in the
  services, so neither door can bypass it.
- **The MCP door offers fewer verbs than the UI door.** Deleting and changing a
  project's state exist only in the UI.

## The app (frontend)

- **The server's types are the app's types.** Ninja's OpenAPI schema →
  `openapi-typescript` → `src/api/schema.d.ts`. A renamed field breaks the
  build, not production.
- **Every read and write is a hook in `src/api/queries.ts`.** Reads are cached
  and shown at once, then refreshed. Capture, reorder, move and delete change
  the cache first and roll back if the server refuses; the server's message
  shows as a toast. Every write ends by refetching (cheap for one user).
- **The rules stay on the server.** The app asks "why?" before a status change
  because the server would refuse it otherwise, not instead of the server.

## Who gets in

- **Two credentials, never mixed.** The app uses Django's session cookie (+
  CSRF). `/mcp` accepts only a bearer token; a session cookie there does
  nothing, and a token does nothing on `/api/`.
- **Django is the authorization server, the MCP SDK only checks tokens.**
  django-oauth-toolkit owns registration, login + consent, tokens and the
  discovery documents. The SDK asks `mcp_tools/auth.py` "is this token valid?",
  which looks it up in DOT's tables. Tokens are stored as hashes.
- **A client finds everything from one 401.** `/mcp` without a token answers
  401 with a link to `/.well-known/oauth-protected-resource/mcp`, which names
  this server as the authorization server; its metadata lists the endpoints.
  The client then registers itself (DCR, or a URL to its own metadata: CIMD),
  sends me to `/oauth/authorize/`, and swaps the code for tokens.
- **One login lock.** The login page and the admin go through django-axes. The
  client IP comes from `CLIENT_IP_HEADER` because behind a tunnel every request
  comes from the tunnel.
- **Disconnect = delete.** Removing a connected app deletes its tokens, so
  access ends on the next request, not when the token expires.

## In production

```
proxy or tunnel (https) ─▶ container :8000 ─▶ uvicorn ─▶ config/asgi.py
                                                          ├─ /mcp   MCP SDK
                                                          └─ rest   Django: WhiteNoise (files)
                                                                    → views → app shell
```

- **One image, one process.** The built React app and Django's static files
  are inside it; nothing in front needs to know about files.
- **The proxy is trusted for two things:** "this came in over https"
  (`X-Forwarded-Proto`) and the visitor's IP (`CLIENT_IP_HEADER`). That's safe
  only because the app's port is bound to loopback and only the proxy reaches it.
- **Data lives outside the image:** `DATA_DIR` (the SQLite file) and
  `BACKUP_DIR` are mounted folders. Replacing the container loses nothing.

## Public surface

`/mcp`, `/oauth/…` and `/.well-known/…` must be reachable from the internet
(claude.ai calls from Anthropic's servers), so they can't sit behind a VPN or
an access proxy. The app's own login (with lockout) is the real lock.
