# discord-mcp

Give Claude read access to your own Discord: DMs, group chats and servers.

A small server listens to your account over Discord's gateway, the way the desktop app does, and saves every message to a local SQLite cache with full-text search. Claude queries the cache through MCP, so looking things up costs Discord nothing. Older history is fetched only when Claude asks for it, then cached.

> Automating a user account is against Discord's Terms of Service. This is read-only and behaves like a normal client, but use it at your own risk.

## Tools

| Tool | What it does |
|---|---|
| `search` | Full-text search across everything cached |
| `recent` | Messages from the last N hours, all channels |
| `list_channels` | Every DM, group and channel seen, newest first |
| `conversation` | One channel's messages in order, pulling older history from Discord if needed |

## Setup

You need Docker, a domain, and an HTTPS reverse proxy (Caddy, nginx, a tunnel, anything).

**1. Your Discord token.** Open Discord in a browser, open DevTools → Network, click any channel, pick a request to `discord.com/api` and copy its `Authorization` header.

**2. A Discord OAuth app** (this is how Claude signs in as you). At [discord.com/developers](https://discord.com/developers/applications) create an application, open OAuth2, copy the Client ID and Secret, and add the redirect `https://<your-domain>/auth/callback`.

**3. Run it.**

```sh
cp .env.example .env   # fill in the token, OAuth app and PUBLIC_URL
docker compose up -d
```

The server listens on `BIND_ADDR:PORT` (default `127.0.0.1:8000`).

**4. Put HTTPS in front.** Point your domain at it. With Caddy:

```
discord-mcp.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

**5. Connect Claude.** In Claude, go to Settings → Connectors → Add custom connector, enter `https://<your-domain>/mcp`, and sign in with Discord.

## Security

Only the Discord account whose token the server runs on can sign in; anyone else gets denied. Still, `data/` holds a copy of your messages and `.env` holds your token, so treat the machine like it is logged into your account. Changing your Discord password revokes the token.

Auth lives in the server rather than the proxy because Claude connectors need OAuth with dynamic client registration. Keep `BIND_ADDR` on a private address so the only way in is through your HTTPS proxy.
