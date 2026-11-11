# Running 311 yourself

311 is one Docker container with one SQLite file. Claude connects to it from
the internet (claude.ai calls it from Anthropic's servers), so it needs a public
**https** address. There are two ways to get one:

- **A. Cloudflare Tunnel** (recommended): a second container connects out to
  Cloudflare. No port is opened on your machine, no certificates to manage.
  Needs a free Cloudflare account. Cloudflare decrypts the traffic on its way
  through.
- **B. Your own reverse proxy** (Caddy, nginx, Traefik…) on a machine that the
  internet can reach on port 443.

Time: about 20 minutes.

## What you need

- A machine that stays on, with Docker and Docker Compose v2. amd64 or arm64:
  a Raspberry Pi 4 or 5 is plenty.
- A domain. The examples use `311.example.com`.
- For A: the domain's DNS at Cloudflare.

## 1. Files and settings

```sh
mkdir 311 && cd 311
mkdir data
curl -fsSL -o .env https://raw.githubusercontent.com/JOL-E/three-one-one/main/.env.example
chmod 600 .env
```

The compose file, for **A**:

```sh
curl -fsSLO https://raw.githubusercontent.com/JOL-E/three-one-one/main/deploy/cloudflare/compose.yaml
```

or for **B**:

```sh
curl -fsSLO https://raw.githubusercontent.com/JOL-E/three-one-one/main/compose.yaml
```

The app runs as user 1000 and must be able to write to `data/`. Check with
`id -u`: if it isn't `1000`, run `sudo chown 1000:1000 data`.

Fill in `.env`:

| Setting | Value |
|---|---|
| `SECRET_KEY` | A long random string: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `BASE_URL` | `https://311.example.com`: your address, no trailing slash |
| `CLIENT_IP_HEADER` | A: `CF-Connecting-IP`. B: `X-Forwarded-For` |
| `TUNNEL_TOKEN` | A only: from step 2A |

Leave the rest as it is. `.env.example` explains every setting.

## 2A. Cloudflare Tunnel

In the Cloudflare dashboard: **Zero Trust → Networks → Tunnels → Create a
tunnel**.

1. Connector type **Cloudflared**, any name (`311`).
2. The next page shows install commands. Copy the long token after `--token`
   (it starts with `eyJ`) into `TUNNEL_TOKEN` in `.env`. Don't run the commands:
   the compose file runs cloudflared for you.
3. Add a **public hostname** (newer dashboards call it a *published
   application route*):

   | Field | Value |
   |---|---|
   | Subdomain | `311` |
   | Domain | `example.com` |
   | Service type | `HTTP` |
   | URL | `app:8000` |

   `app` is the 311 container's name on the compose network.

Two things not to put in front of it:

- **No Cloudflare Access** on this hostname. claude.ai calls `/mcp`, `/oauth/`
  and `/.well-known/` from Anthropic's servers and can't pass Access. 311's own
  login, with a lockout after five wrong passwords, protects it.
- **Bot Fight Mode** and some WAF rules block Anthropic's servers too. If
  claude.ai can't connect, look under **Security → Events** for the domain.

## 2B. Your own reverse proxy

The compose file publishes the app on `127.0.0.1:8000`, this machine only.
Your proxy must:

1. Serve **https** with a valid certificate. claude.ai refuses anything else.
2. Pass on the original `Host` header. The app answers only to `BASE_URL`'s host.
3. Send `X-Forwarded-Proto: https`.
4. Send the visitor's IP in `X-Forwarded-For`. The app uses the last entry,
   the one your proxy added.
5. Not buffer responses, and allow long requests to `/mcp`: Claude keeps one
   open to receive events.
6. Be the only way to reach the app. Keep the port on `127.0.0.1`: anyone who
   reaches the app directly could fake `X-Forwarded-For`.
7. Have no login of its own in front (basic auth, SSO), for the same reason as
   Cloudflare Access above.

With **Caddy** on the same machine, this is the whole Caddyfile. It gets the
certificate by itself and covers points 1 to 5 by default:

```
311.example.com {
	reverse_proxy 127.0.0.1:8000
}
```

With **nginx**, set `proxy_set_header Host $host;`,
`proxy_set_header X-Forwarded-Proto https;`,
`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`,
`proxy_buffering off;` and `proxy_read_timeout 1h;`.

## 3. Start and log in

```sh
docker compose up -d
docker compose ps
```

After about half a minute the app shows `(healthy)`. Then create your login:

```sh
docker compose exec app python manage.py createsuperuser
```

Check from any computer:

```sh
curl -sI https://311.example.com/login/ | grep -i -E '^(HTTP|strict-transport)'
curl -s https://311.example.com/.well-known/oauth-protected-resource/mcp; echo
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://311.example.com/mcp
```

Expected:

```
HTTP/2 200
strict-transport-security: max-age=31536000
{"resource": "https://311.example.com/mcp", "authorization_servers": ["https://311.example.com"], ...}
401
```

`401` is right: Claude has to log in first. If the `strict-transport-security`
line is missing, the proxy isn't sending `X-Forwarded-Proto: https`.

Open `https://311.example.com` and log in. On a phone, add it to the home
screen (Safari: Share → Add to Home Screen) and it opens like an app.

## 4. Connect Claude

**claude.ai** (web; the phone apps pick it up from your account): Settings →
Connectors → **Add custom connector**, URL `https://311.example.com/mcp`, then
**Connect**. Your 311 login opens; allow access.

**Claude Code:**

```sh
claude mcp add --transport http --scope user 311 https://311.example.com/mcp
```

Then `/mcp` in Claude Code → `311` → Authenticate.

Every connection is listed in 311 under Settings → Connected apps, where you can
end it.

## 5. Backups

```sh
docker compose exec app python manage.py backup
```

This copies the database to `data/backups/` (safe while the app runs, checked
before it counts) and keeps the newest 7. Run it nightly, for example with
`crontab -e`:

```
0 3 * * * cd /path/to/311 && docker compose exec -T app python manage.py backup > /dev/null
```

`data/backups/` sits on the same disk as the database. Copy it somewhere else
too (another disk, restic, rclone…).

**Restore:**

```sh
docker compose stop app
cp data/backups/311_<date>.sqlite3 data/311.sqlite3
docker compose start app
```

## 6. Updates

The image is rebuilt on every change and weekly, for security fixes in its base
image. To update (with a backup first, in case a migration goes wrong):

```sh
docker compose exec app python manage.py backup
docker compose pull && docker compose up -d
```

**Roll back:** every build is also tagged `sha-` plus a commit hash (see the
package page on GitHub). Put that tag in place of `latest` in `compose.yaml`,
`docker compose up -d`, and restore the backup if the newer version had already
changed the database.

## Troubleshooting

- **Logs:** `docker compose logs --tail 100 app`
- **Bad Request (400):** the address you opened isn't `BASE_URL`'s host.
- **Locked out after wrong passwords:** wait 15 minutes, or
  `docker compose exec app python manage.py axes_reset`.
- **Everyone is locked out at once:** `CLIENT_IP_HEADER` is empty or wrong, so
  every visitor looks like the proxy.
- **Cloudflare error 1033:** cloudflared isn't running or has the wrong token:
  `docker compose logs cloudflared`.
- **Cloudflare 502:** the hostname's URL isn't `app:8000`, or the app isn't
  healthy yet.
- **claude.ai "couldn't connect"** while the checks in step 3 pass: see Bot Fight
  Mode in 2A, or your proxy's login (2B, point 7).
