"""SQLite persistence for conversation history and the activity event log."""

import json
import os
import sqlite3
from pathlib import Path

_db_path_override = os.environ.get("HANNAH_DB")
DB_PATH = Path(_db_path_override) if _db_path_override else Path.home() / ".hannah" / "missioncontrol.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                role     TEXT NOT NULL,
                content  TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                type     TEXT NOT NULL,
                payload  TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


def save_message(role: str, content) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)",
            (role, json.dumps(content) if not isinstance(content, str) else content),
        )


def load_messages(limit: int = 200) -> list:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    result = []
    for r in reversed(rows):
        try:
            content = json.loads(r["content"])
        except (json.JSONDecodeError, TypeError):
            content = r["content"]
        result.append({"role": r["role"], "content": content})
    return result


def save_event(event: dict) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO events (type, payload) VALUES (?, ?)",
            (event["type"], json.dumps(event)),
        )


def load_events(limit: int = 200) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT payload FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [json.loads(r["payload"]) for r in reversed(rows)]
