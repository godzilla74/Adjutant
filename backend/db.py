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

            CREATE TABLE IF NOT EXISTS social_drafts (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id        TEXT NOT NULL REFERENCES products(id),
                platform          TEXT NOT NULL,
                content           TEXT NOT NULL,
                image_description TEXT,
                status            TEXT NOT NULL DEFAULT 'pending_review',
                review_item_id    INTEGER REFERENCES review_items(id),
                created_at        TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_social_drafts_product
                ON social_drafts(product_id, status);
        """)
        # Add brand config columns to products (idempotent)
        _brand_cols = [
            ("brand_voice",     "TEXT"),
            ("tone",            "TEXT"),
            ("writing_style",   "TEXT"),
            ("target_audience", "TEXT"),
            ("social_handles",  "TEXT"),  # JSON: {"instagram": "@handle", ...}
            ("hashtags",        "TEXT"),  # comma-separated
            ("brand_notes",     "TEXT"),
        ]
        for col_name, col_type in _brand_cols:
            try:
                conn.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass  # column already exists
        _seed_products(conn)


def _seed_products(conn: sqlite3.Connection) -> None:
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


def create_product(id: str, name: str, icon_label: str, color: str) -> str:
    with _conn() as conn:
        existing = conn.execute("SELECT id FROM products WHERE id = ?", (id,)).fetchone()
        if existing:
            return f"Product '{id}' already exists."
        conn.execute(
            "INSERT INTO products (id, name, icon_label, color) VALUES (?, ?, ?, ?)",
            (id, name, icon_label, color),
        )
    return f"Created product: {name} (id: {id})"


def update_product(product_id: str, **kwargs) -> str:
    """Update any product fields. Accepted kwargs: name, icon_label, color,
    brand_voice, tone, writing_style, target_audience, social_handles, hashtags, brand_notes."""
    allowed = {"name", "icon_label", "color", "brand_voice", "tone",
               "writing_style", "target_audience", "social_handles", "hashtags", "brand_notes"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return "No valid fields to update."
    cols = ", ".join(f"{k} = ?" for k in updates)
    with _conn() as conn:
        conn.execute(
            f"UPDATE products SET {cols} WHERE id = ?",
            (*updates.values(), product_id),
        )
    return f"Updated product '{product_id}': {', '.join(updates.keys())}"


def delete_product(product_id: str) -> str:
    with _conn() as conn:
        row = conn.execute("SELECT name FROM products WHERE id = ?", (product_id,)).fetchone()
        if not row:
            return f"Product '{product_id}' not found."
        # Delete child records first (FK enforcement)
        for table in ("messages", "review_items", "activity_events", "social_drafts", "objectives", "workstreams"):
            conn.execute(f"DELETE FROM {table} WHERE product_id = ?", (product_id,))
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    return f"Deleted product: {row['name']}"


def get_product_config(product_id: str) -> dict:
    """Return full product row including brand config fields."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return dict(row) if row else {}


# ── Workstreams ───────────────────────────────────────────────────────────────

def create_workstream(product_id: str, name: str, status: str = "paused") -> str:
    with _conn() as conn:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(display_order), -1) FROM workstreams WHERE product_id = ?",
            (product_id,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO workstreams (product_id, name, status, display_order) VALUES (?, ?, ?, ?)",
            (product_id, name, status, max_order + 1),
        )
    return f"Created workstream: {name}"


def update_workstream_status(product_id: str, name_fragment: str, status: str) -> str:
    if status not in ("running", "warn", "paused"):
        return f"Invalid status '{status}'. Must be: running, warn, paused."
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, name FROM workstreams WHERE product_id = ? AND name LIKE ? LIMIT 1",
            (product_id, f"%{name_fragment}%"),
        ).fetchone()
        if not row:
            return f"No workstream matching '{name_fragment}' found."
        conn.execute("UPDATE workstreams SET status = ? WHERE id = ?", (status, row["id"]))
    return f"Updated '{row['name']}' → {status}"


def delete_workstream(product_id: str, name_fragment: str) -> str:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, name FROM workstreams WHERE product_id = ? AND name LIKE ? LIMIT 1",
            (product_id, f"%{name_fragment}%"),
        ).fetchone()
        if not row:
            return f"No workstream matching '{name_fragment}' found."
        conn.execute("DELETE FROM workstreams WHERE id = ?", (row["id"],))
    return f"Deleted workstream: {row['name']}"


def get_workstreams(product_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, name, status, display_order FROM workstreams WHERE product_id = ? ORDER BY display_order",
            (product_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Objectives ────────────────────────────────────────────────────────────────

def create_objective(
    product_id: str,
    text: str,
    progress_current: int = 0,
    progress_target: int | None = None,
) -> str:
    """Create a new objective for a product. Returns a status string."""
    with _conn() as conn:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(display_order), -1) FROM objectives WHERE product_id = ?",
            (product_id,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO objectives (product_id, text, progress_current, progress_target, display_order) VALUES (?, ?, ?, ?, ?)",
            (product_id, text, progress_current, progress_target, max_order + 1),
        )
    return f"Created objective: \"{text}\""


def update_objective(
    product_id: str,
    text_fragment: str,
    progress_current: int,
    progress_target: int | None = None,
) -> str:
    """Update progress on an objective matched by partial text. Returns a status string."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, text FROM objectives WHERE product_id = ? AND text LIKE ? ORDER BY display_order LIMIT 1",
            (product_id, f"%{text_fragment}%"),
        ).fetchone()
        if not row:
            return f"No objective matching '{text_fragment}' found for {product_id}."
        if progress_target is not None:
            conn.execute(
                "UPDATE objectives SET progress_current = ?, progress_target = ? WHERE id = ?",
                (progress_current, progress_target, row["id"]),
            )
        else:
            conn.execute(
                "UPDATE objectives SET progress_current = ? WHERE id = ?",
                (progress_current, row["id"]),
            )
    return f"Updated: \"{row['text']}\" → {progress_current}"


def get_objectives(product_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, text, progress_current, progress_target, display_order FROM objectives WHERE product_id = ? ORDER BY display_order",
            (product_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_objective(product_id: str, text_fragment: str) -> str:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, text FROM objectives WHERE product_id = ? AND text LIKE ? LIMIT 1",
            (product_id, f"%{text_fragment}%"),
        ).fetchone()
        if not row:
            return f"No objective matching '{text_fragment}' found."
        conn.execute("DELETE FROM objectives WHERE id = ?", (row["id"],))
    return f"Deleted objective: {row['text']}"


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
    if action not in ("approved", "skipped"):
        raise ValueError(f"action must be 'approved' or 'skipped', got {action!r}")
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


def load_messages(product_id: str, limit: int = 200) -> list[dict]:
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


# ── Social drafts ─────────────────────────────────────────────────────────────

def save_social_draft(
    product_id: str,
    platform: str,
    content: str,
    image_description: str = "",
    review_item_id: int | None = None,
) -> int:
    with _conn() as conn:
        cursor = conn.execute(
            "INSERT INTO social_drafts (product_id, platform, content, image_description, review_item_id) VALUES (?, ?, ?, ?, ?)",
            (product_id, platform, content, image_description, review_item_id),
        )
    return cursor.lastrowid


def list_social_drafts(product_id: str, status: str = "pending_review") -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM social_drafts WHERE product_id = ? AND status = ? ORDER BY created_at DESC",
            (product_id, status),
        ).fetchall()
    return [dict(r) for r in rows]
