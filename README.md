# discord-mcp

Read-only access to your own Discord (DMs, group chats and servers) for Claude or any MCP client.

A small server stays connected to your account the way the desktop app does and keeps every message in a local SQLite cache with full-text search. Lookups hit the cache, not Discord; older history is fetched only when asked for, then cached.

> Automating a user account is against Discord's Terms of Service. This only reads and behaves like a normal client, but use it at your own risk.

| Tool | |
|---|---|
| `search` | Full-text search, optionally within one channel |
| `recent` | Everything from the last N hours |
| `list_channels` | Every DM, group and channel, most recent first |
| `conversation` | One channel in order, fetching older history as needed |
| `attachment` | Images the model can see, PDFs and text it can read, plus a fresh download link |

## Setup

You need Docker, a domain, an HTTPS reverse proxy, and two things from Discord:

- **Your account token**: in Discord on the web, open DevTools → Network, click any channel, and copy the `Authorization` header of a `discord.com/api` request.
- **An OAuth app** (that's how Claude signs in as you; only your account gets in): at [discord.com/developers](https://discord.com/developers/applications), create one, copy its Client ID and Secret, and add the redirect `https://<your-domain>/auth/callback`.

```sh
cp .env.example .env    # fill it in
docker compose up -d
```

Put HTTPS in front (Caddy: `reverse_proxy 127.0.0.1:8000`), then add `https://<your-domain>/mcp` in Claude under Settings → Connectors.

Runs comfortably on a Raspberry Pi 4: writes are batched once a minute, logs are capped, and the container is non-root and read-only. The data volume holds a copy of your messages and `.env` holds your token, so treat the machine like it's logged into your account. Changing your Discord password revokes the token.

## Contributing

Issues and PRs welcome, including from agents using the server. CI builds every push.
