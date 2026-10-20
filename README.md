# discord-mcp

An MCP server with read-only access to your own Discord: DMs, group chats and servers.

It stays connected to your account the way the desktop app does and keeps every message in a local SQLite cache with full-text search. Lookups hit the cache, not Discord; older history is fetched only when asked for, then cached.

> Automating a user account is against Discord's Terms of Service. This only reads and behaves like a normal client, but use it at your own risk.

| Tool | |
|---|---|
| `search` | Full-text search, optionally within one channel |
| `recent` | Everything from the last N hours |
| `list_channels` | Every DM, group and channel, most recent first |
| `conversation` | One channel in order, fetching older history as needed |
| `attachment` | Images the model can see, PDFs and text it can read, plus a download link |

## Your token

In Discord on the web, open DevTools → Network, click any channel, and copy the `Authorization` header of a `discord.com/api` request. The server reads it from `DISCORD_TOKEN`. Treat it like your password; changing your password revokes it.

## Use it locally

```sh
pip install -r requirements.txt
claude mcp add discord -e DISCORD_TOKEN=<token> -- python /path/to/discord-mcp/server.py
```

Any MCP client works the same way: run `server.py` as a stdio server with `DISCORD_TOKEN` set.

## Host it

To reach it from anywhere (phone, web), run it over HTTP behind any HTTPS reverse proxy. Fill in `.env` from `.env.example` (your URL and an OAuth app so only you can sign in; a Discord app works with no extra config), then:

```sh
docker compose up -d
```

Add `https://<your-domain>/mcp` to your client as a remote server. The cache volume holds a copy of your messages, so keep the machine private.

## Contributing

Issues and PRs welcome, including from agents using the server.
