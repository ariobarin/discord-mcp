"""SQLite message cache with full-text search."""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY,
    channel_id  INTEGER NOT NULL,
    channel     TEXT NOT NULL,
    guild       TEXT,
    author      TEXT NOT NULL,
    content     TEXT NOT NULL,
    attachments TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    edited_at   TEXT
);
CREATE INDEX IF NOT EXISTS messages_channel_time ON messages (channel_id, created_at);
CREATE INDEX IF NOT EXISTS messages_time ON messages (created_at);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content, author, channel, content='messages', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts (rowid, content, author, channel)
    VALUES (new.id, new.content, new.author, new.channel);
END;
CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts (messages_fts, rowid, content, author, channel)
    VALUES ('delete', old.id, old.content, old.author, old.channel);
    INSERT INTO messages_fts (rowid, content, author, channel)
    VALUES (new.id, new.content, new.author, new.channel);
END;
"""

COLUMNS = "id, channel_id, channel, guild, author, content, attachments, created_at, edited_at"


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("PRAGMA journal_mode=WAL;" + SCHEMA)

    def save(self, rows: list[dict]) -> None:
        self.db.executemany(
            f"""INSERT INTO messages ({COLUMNS})
                VALUES (:id, :channel_id, :channel, :guild, :author, :content,
                        :attachments, :created_at, :edited_at)
                ON CONFLICT (id) DO UPDATE SET
                    content = excluded.content,
                    attachments = excluded.attachments,
                    edited_at = excluded.edited_at""",
            rows,
        )
        self.db.commit()

    def search(self, query: str, limit: int) -> list[dict]:
        sql = f"""SELECT {", ".join("m." + c for c in COLUMNS.split(", "))}
                  FROM messages_fts f JOIN messages m ON m.id = f.rowid
                  WHERE messages_fts MATCH ? ORDER BY m.created_at DESC LIMIT ?"""
        return [dict(r) for r in self.db.execute(sql, (query, limit))]

    def recent(self, since: str, limit: int) -> list[dict]:
        sql = f"SELECT {COLUMNS} FROM messages WHERE created_at >= ? ORDER BY created_at DESC LIMIT ?"
        return [dict(r) for r in self.db.execute(sql, (since, limit))]

    def conversation(self, channel_id: int, before: str | None, limit: int) -> list[dict]:
        sql = f"""SELECT {COLUMNS} FROM messages
                  WHERE channel_id = ? AND created_at < ? ORDER BY created_at DESC LIMIT ?"""
        rows = self.db.execute(sql, (channel_id, before or "9999", limit))
        return [dict(r) for r in rows][::-1]

    def oldest(self, channel_id: int) -> str | None:
        row = self.db.execute(
            "SELECT MIN(created_at) FROM messages WHERE channel_id = ?", (channel_id,)
        ).fetchone()
        return row[0]

    def channels(self) -> list[dict]:
        sql = """SELECT channel_id, channel, guild, COUNT(*) AS messages,
                        MAX(created_at) AS last_message
                 FROM messages GROUP BY channel_id ORDER BY last_message DESC"""
        return [dict(r) for r in self.db.execute(sql)]
