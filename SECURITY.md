# Security

## Reporting a vulnerability

Please don't open a public issue. Report it privately through GitHub instead:
**Security → Report a vulnerability** on this repository
([direct link](https://github.com/JOL-E/three-one-one/security/advisories/new)).

Say what you found, how to reproduce it, and what an attacker could do with it.
311 is maintained by one person in their spare time: expect a first answer
within a week. Once a fix is out, the advisory is published, with credit to
you if you like.

## Supported versions

Only the newest image (`ghcr.io/jol-e/three-one-one:latest`, built from `main`)
gets fixes. Update with `docker compose pull && docker compose up -d`
([docs/self-hosting.md](docs/self-hosting.md)).

## In scope

The app, its API, the MCP server, the OAuth server and login, and the Docker
image. Problems in your own setup (proxy, tunnel, host) are out of scope unless
the guide told you to do something unsafe; then it's a bug in the guide.
