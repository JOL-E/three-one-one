# Roadmap

In order. Each milestone ends with something that works and that I understand.

- **M0 Repo:** docs, decisions, license, private-data guard. ✅
- **M1 Spike, MCP from the inside:** Django project skeleton plus an MCP
  endpoint with one or two tools (`list_items`, `add_item`) on a throwaway
  model, connected to Claude Code on the Mac over `localhost`, **no auth**.
  Goal: see every request and response, prove Django + the async MCP SDK work
  together. Decide the project layout here. ✅
- **M2 Data model:** Project, Item, Activity with the states and rules from
  DECISIONS; admin; tests for every rule. ✅
- **M3 Full tool set:** the tools from DECISIONS #7, rules enforced by the
  server, tool descriptions written and tested with Claude. ✅
- **M4 UI:** React PWA. Quick capture, inbox, drag-to-sort, move to project,
  project views, item detail with activity. Native feel on iPhone and Mac. ✅
- **M5 Auth:** login + lockout, OAuth (authorization server + metadata +
  automatic registration), connected apps page. Then claude.ai can connect. ✅
- **M6 Ship:** Docker image, CI with multi-arch builds and weekly rebuilds,
  backups, running on my Pi, connected as a custom connector in claude.ai.
  Then import the items parked in my private context repo and delete that list. ✅
- **M7 Public:** self-hosting docs (Cloudflare Tunnel and Caddy), SECURITY.md,
  a history check, flip the repo to public.

**Later:** smaller work and ideas are items in 311 itself (project 311).
