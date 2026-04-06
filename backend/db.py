# backend/db.py
"""SQLite persistence — multi-product schema with WAL mode."""

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

from backend.seed_data import OBJECTIVES, PRODUCTS, WORKSTREAMS

_db_path_override = os.environ.get("HANNAH_DB")
DB_PATH = Path(_db_path_override) if _db_path_override else Path.home() / ".hannah" / "missioncontrol.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id         TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                icon_label TEXT NOT NULL,
                color      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workstreams (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id    TEXT NOT NULL REFERENCES products(id),
                name          TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'paused',
                display_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS objectives (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id       TEXT NOT NULL REFERENCES products(id),
                text             TEXT NOT NULL,
                progress_current INTEGER NOT NULL DEFAULT 0,
                progress_target  INTEGER,
                display_order    INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS activity_events (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id     TEXT NOT NULL REFERENCES products(id),
                agent_type     TEXT NOT NULL,
                headline       TEXT NOT NULL,
                rationale      TEXT NOT NULL DEFAULT '',
                status         TEXT NOT NULL DEFAULT 'running',
                output_preview TEXT,
                summary        TEXT,
                created_at     TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS review_items (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id        TEXT NOT NULL REFERENCES products(id),
                activity_event_id INTEGER REFERENCES activity_events(id),
                title             TEXT NOT NULL,
                description       TEXT NOT NULL,
                risk_label        TEXT NOT NULL,
                status            TEXT NOT NULL DEFAULT 'pending',
                created_at        TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL REFERENCES products(id),
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_activity_events_product
                ON activity_events(product_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_review_items_product
                ON review_items(product_id, status);
            CREATE INDEX IF NOT EXISTS idx_messages_product
                ON messages(product_id, id);
        """)
    _seed_products()


def _seed_products() -> None:
    with _conn() as conn:
        for p in PRODUCTS:
            conn.execute(
                "INSERT OR IGNORE INTO products (id, name, icon_label, color) VALUES (?, ?, ?, ?)",
                (p["id"], p["name"], p["icon_label"], p["color"]),
            )
            existing = conn.execute(
                "SELECT COUNT(*) FROM workstreams WHERE product_id = ?", (p["id"],)
            ).fetchone()[0]
            if existing == 0:
                for ws in WORKSTREAMS.get(p["id"], []):
                    conn.execute(
                        "INSERT INTO workstreams (product_id, name, status, display_order) VALUES (?, ?, ?, ?)",
                        (p["id"], ws["name"], ws["status"], ws["display_order"]),
                    )
                for obj in OBJECTIVES.get(p["id"], []):
                    conn.execute(
                        "INSERT INTO objectives (product_id, text, progress_current, progress_target, display_order) VALUES (?, ?, ?, ?, ?)",
                        (p["id"], obj["text"], obj["progress_current"], obj["progress_target"], obj["display_order"]),
                    )


# ── Products ──────────────────────────────────────────────────────────────────

def get_products() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT id, name, icon_label, color FROM products").fetchall()
    return [dict(r) for r in rows]


# ── Workstreams ───────────────────────────────────────────────────────────────

def get_workstreams(product_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, name, status, display_order FROM workstreams WHERE product_id = ? ORDER BY display_order",
            (product_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Objectives ────────────────────────────────────────────────────────────────

def get_objectives(product_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, text, progress_current, progress_target, display_order FROM objectives WHERE product_id = ? ORDER BY display_order",
            (product_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Activity events ───────────────────────────────────────────────────────────

def save_activity_event(
    product_id: str,
    agent_type: str,
    headline: str,
    rationale: str,
    status: str = "running",
    output_preview: Optional[str] = None,
) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO activity_events
               (product_id, agent_type, headline, rationale, status, output_preview)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (product_id, agent_type, headline, rationale, status, output_preview),
        )
        return cur.lastrowid


def update_activity_event(
    event_id: int,
    status: str,
    summary: Optional[str] = None,
    output_preview: Optional[str] = None,
) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE activity_events SET status = ?, summary = ?, output_preview = COALESCE(?, output_preview) WHERE id = ?",
            (status, summary, output_preview, event_id),
        )


def load_activity_events(product_id: str, limit: int = 100) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, agent_type, headline, rationale, status, output_preview, summary, created_at
               FROM activity_events WHERE product_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (product_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


# ── Review items ──────────────────────────────────────────────────────────────

def save_review_item(
    product_id: str,
    title: str,
    description: str,
    risk_label: str,
    activity_event_id: Optional[int] = None,
) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO review_items (product_id, activity_event_id, title, description, risk_label)
               VALUES (?, ?, ?, ?, ?)""",
            (product_id, activity_event_id, title, description, risk_label),
        )
        return cur.lastrowid


def resolve_review_item(item_id: int, action: str) -> None:
    """action: 'approved' | 'skipped'"""
    with _conn() as conn:
        conn.execute(
            "UPDATE review_items SET status = ? WHERE id = ?",
            (action, item_id),
        )


def load_review_items(product_id: str, status: str = "pending") -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, activity_event_id, title, description, risk_label, status, created_at
               FROM review_items WHERE product_id = ? AND status = ?
               ORDER BY created_at""",
            (product_id, status),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Messages ──────────────────────────────────────────────────────────────────

def save_message(product_id: str, role: str, content) -> None:
    serialized = json.dumps(content) if not isinstance(content, str) else content
    with _conn() as conn:
        conn.execute(
            "INSERT INTO messages (product_id, role, content) VALUES (?, ?, ?)",
            (product_id, role, serialized),
        )


def load_messages(product_id: str, limit: int = 200) -> list:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE product_id = ? ORDER BY id DESC LIMIT ?",
            (product_id, limit),
        ).fetchall()
    result = []
    for r in reversed(rows):
        try:
            content = json.loads(r["content"])
        except (json.JSONDecodeError, TypeError):
            content = r["content"]
        result.append({"role": r["role"], "content": content})
    return result
