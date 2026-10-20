"""SQLite message cache with full-text search.

Writes are committed in batches (see `commit`) to spare SD cards and other flash storage.
"""

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
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;" + SCHEMA)

    def save(self, rows: list[dict]) -> None:
        """Upsert messages. Not committed until `commit`; this connection already sees them."""
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

    def commit(self) -> None:
        self.db.commit()

    def _rows(self, sql: str, *args) -> list[dict]:
        return [dict(r) for r in self.db.execute(sql, args)]

    def search(self, query: str, limit: int, channel_id: int | None = None) -> list[dict]:
        cols = ", ".join("m." + c for c in COLUMNS.split(", "))
        sql = f"""SELECT {cols} FROM messages_fts f JOIN messages m ON m.id = f.rowid
                  WHERE messages_fts MATCH ? AND (? IS NULL OR m.channel_id = ?)
                  ORDER BY m.created_at DESC LIMIT ?"""
        try:
            return self._rows(sql, query, channel_id, channel_id, limit)
        except sqlite3.OperationalError:
            # Plain text with stray punctuation isn't valid FTS5 syntax; search the words literally.
            words = " ".join('"' + w.replace('"', '""') + '"' for w in query.split())
            return self._rows(sql, words, channel_id, channel_id, limit) if words else []

    def recent(self, since: str, limit: int) -> list[dict]:
        return self._rows(
            f"SELECT {COLUMNS} FROM messages WHERE created_at >= ? ORDER BY created_at DESC LIMIT ?",
            since, limit,
        )

    def conversation(self, channel_id: int, before: str | None, limit: int) -> list[dict]:
        """Up to `limit` messages before `before` (default: now), oldest first."""
        rows = self._rows(
            f"""SELECT {COLUMNS} FROM messages WHERE channel_id = ? AND created_at < ?
                ORDER BY created_at DESC LIMIT ?""",
            channel_id, before or "9999", limit,
        )
        return rows[::-1]

    def channels(self) -> list[dict]:
        return self._rows(
            """SELECT channel_id, channel, guild, COUNT(*) AS messages, MAX(created_at) AS last_message
               FROM messages GROUP BY channel_id ORDER BY last_message DESC"""
        )
