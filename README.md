# 311

**An inbox for your side-project ideas that Claude can reach.**

You have ideas everywhere: on the subway, in the middle of a coding session, in
a chat with Claude. 311 is one place for all of them. Capture an idea in a
second, sort your inbox later, move items into projects, and watch a few of
them grow into real projects.

Named after New York's 311 line, where you can report anything: it gets a
number, goes to the right place and is tracked until it's closed.

- **A fast, phone-friendly app** for capturing, sorting and prioritizing.
- **An MCP server**, so Claude (claude.ai on web and phone, Claude Code, and
  other MCP clients) can add, write up and update items for you, with you
  deciding what it may do.
- **Self-hosted, single user.** One Docker container, one SQLite file.

> **Status:** young, in daily use by its author. Expect changes.

## What you get

### The app

- **Capture in a second.** Type the idea, it lands in your inbox. Sort later.
- **Projects with a state:** idea, building, live or archived, with an optional
  link to the repo. One permanent project, *General*, holds things to look into
  that will never be a project of their own.
- **Items move from open to doing to done.** A project's open items are in your
  priority order: drag to reorder. Every status change asks why, and the answer
  goes into the item's activity log, next to comments and every other change.
- **Search** across the inbox and every project. Items have short ids like
  `#3F9A`, the same ones Claude uses.
- **Feels like a native app.** Add it to your iPhone's home screen: swipe back
  from the edge, swipe rows to move or delete, sheets that slide up. On a Mac,
  list and detail sit side by side. Dark by default, light if you prefer.
- **Connected apps:** every Claude you've connected is listed in Settings, and
  disconnecting one ends its access at once.

### What Claude can do

Connect Claude once, then talk to it as usual:

- *"Add this to 311: a CLI that renames photos by date."*
- *"What's the top open item in project Garden app?"*
- *"Write up #3F9A with what we just worked out."*
- *"Mark #3F9A done: it shipped today."*

Claude can list and read projects and items, add items (to the inbox or a
project), write up their details, comment, change their status, move them
between projects, reorder a project's priorities (it asks you first, where the
client supports that), and create or edit projects.

What Claude **can't** do: delete anything, or change a project's state. Those
are yours, in the app. The rules are enforced by the server, not just written
in the tool descriptions: a status change without a reason is refused, whoever
sends it.

### How Claude connects

311 is a remote MCP server with its own OAuth login. Add your 311's address as
a custom connector in claude.ai (it carries over to the Claude apps on your
phone), or with `claude mcp add` in Claude Code. A login page from your 311
opens, you allow access, done. No keys to copy. Tested with claude.ai and
Claude Code; other MCP clients that support OAuth should work too.

## Run it yourself

One container on any machine with Docker (a Raspberry Pi is plenty), reached
through a Cloudflare Tunnel or your own reverse proxy. Step by step:
[docs/self-hosting.md](docs/self-hosting.md).

## License

MIT, see [LICENSE](LICENSE).
