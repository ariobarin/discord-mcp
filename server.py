"""Read-only Discord MCP server: caches your account's messages and serves them to Claude."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from fastmcp import FastMCP
from fastmcp.server.auth.providers.discord import DiscordProvider
from fastmcp.server.middleware import AuthMiddleware

from store import Store

DATA = Path(os.environ.get("DATA_DIR", "data"))
store = Store(DATA / "messages.db")
client = discord.Client()
log = logging.getLogger("discord-mcp")


def channel_label(channel) -> str:
    if isinstance(channel, discord.DMChannel):
        return f"DM with {channel.recipient}"
    if isinstance(channel, discord.GroupChannel):
        return channel.name or ", ".join(str(u) for u in channel.recipients)
    return f"#{channel.name}"


def to_row(m: discord.Message) -> dict:
    return {
        "id": m.id,
        "channel_id": m.channel.id,
        "channel": channel_label(m.channel),
        "guild": m.guild.name if m.guild else None,
        "author": str(m.author),
        "content": m.content,
        "attachments": " ".join(a.url for a in m.attachments),
        "created_at": m.created_at.isoformat(),
        "edited_at": m.edited_at.isoformat() if m.edited_at else None,
    }


@client.event
async def on_ready():
    log.info("Listening as %s", client.user)


@client.event
async def on_message(m: discord.Message):
    store.save([to_row(m)])


@client.event
async def on_message_edit(_, m: discord.Message):
    store.save([to_row(m)])


def exit_on_failure(task: asyncio.Task) -> None:
    """If the Discord connection dies (bad token, ban), stop so the container restarts and it shows in logs."""
    if not task.cancelled() and task.exception():
        log.error("Discord client stopped: %r", task.exception())
        os._exit(1)


@asynccontextmanager
async def lifespan(_):
    task = asyncio.create_task(client.start(os.environ["DISCORD_TOKEN"]))
    task.add_done_callback(exit_on_failure)
    yield
    await client.close()
    task.cancel()


def is_owner(ctx) -> bool:
    """Only the Discord account whose token this server runs on may use it."""
    return bool(ctx.token and client.user and ctx.token.claims.get("sub") == str(client.user.id))


auth = DiscordProvider(
    client_id=os.environ["DISCORD_CLIENT_ID"],
    client_secret=os.environ["DISCORD_CLIENT_SECRET"],
    base_url=os.environ["PUBLIC_URL"],
)
mcp = FastMCP(
    "Discord",
    instructions="Read-only access to the owner's Discord messages (DMs, group chats, servers). "
    "Times are UTC. Use list_channels to find channel ids.",
    auth=auth,
    middleware=[AuthMiddleware(auth=is_owner)],
    lifespan=lifespan,
)


@mcp.tool
def search(query: str, limit: int = 50) -> list[dict]:
    """Full-text search over cached messages, newest first. Supports FTS5 syntax: "exact phrase", OR, NOT, prefix*."""
    return store.search(query, limit)


@mcp.tool
def recent(hours: float = 24, limit: int = 200) -> list[dict]:
    """Messages from the last N hours across every channel, newest first."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    return store.recent(since.isoformat(), limit)


@mcp.tool
def list_channels() -> list[dict]:
    """Every cached DM, group chat and server channel, most recently active first."""
    return store.channels()


@mcp.tool
async def conversation(channel_id: str, before: str | None = None, limit: int = 50) -> list[dict]:
    """Messages in one channel, oldest to newest, ending before an ISO timestamp (default: now).
    Reads the cache; only asks Discord when the cache runs out, and caches what it gets."""
    cid = int(channel_id)
    rows = store.conversation(cid, before, limit)
    if len(rows) < limit:
        channel = client.get_channel(cid) or await client.fetch_channel(cid)
        oldest = store.oldest(cid)
        start = min(filter(None, [before, oldest]), default=None)
        older = [m async for m in channel.history(
            limit=limit - len(rows),
            before=datetime.fromisoformat(start) if start else None,
        )]
        store.save([to_row(m) for m in older])
        rows = store.conversation(cid, before, limit)
    return rows


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="http", host="0.0.0.0", port=8000, show_banner=False)
