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

## Public surface

`/mcp`, `/oauth/…` and `/.well-known/…` must be reachable from the internet
(claude.ai calls from Anthropic's servers), so they can't sit behind a VPN or
an access proxy. The app's own login (with lockout) is the real lock.
