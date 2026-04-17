# backend/db.py
"""SQLite persistence — multi-product schema with WAL mode."""

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

from backend.seed_data import get_seed_products


def _default_db_path() -> Path:
    import sys
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Adjutant"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home()))) / "Adjutant"
    else:  # Linux and anything else
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "Adjutant"
    base.mkdir(parents=True, exist_ok=True)
    return base / "adjutant.db"


_db_path_override = os.environ.get("AGENT_DB")
DB_PATH = Path(_db_path_override) if _db_path_override else _default_db_path()
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

            CREATE TABLE IF NOT EXISTS conversation_summaries (
                product_id          TEXT PRIMARY KEY REFERENCES products(id),
                summary             TEXT NOT NULL DEFAULT '',
                last_summarized_id  INTEGER NOT NULL DEFAULT 0,
                updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS social_drafts (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id        TEXT NOT NULL REFERENCES products(id),
                platform          TEXT NOT NULL,
                content           TEXT NOT NULL,
                image_description TEXT,
                image_url         TEXT,
                status            TEXT NOT NULL DEFAULT 'pending_review',
                review_item_id    INTEGER REFERENCES review_items(id),
                post_url          TEXT,
                created_at        TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_social_drafts_product
                ON social_drafts(product_id, status);

            CREATE TABLE IF NOT EXISTS directive_templates (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id    TEXT NOT NULL REFERENCES products(id),
                label         TEXT NOT NULL,
                content       TEXT NOT NULL,
                display_order INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_directive_templates_product
                ON directive_templates(product_id, display_order);

            CREATE TABLE IF NOT EXISTS model_config (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS product_notes (
                product_id TEXT PRIMARY KEY REFERENCES products(id),
                content    TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS directive_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL REFERENCES products(id),
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_directive_history_product
                ON directive_history(product_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS mcp_servers (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                type       TEXT NOT NULL,
                url        TEXT,
                command    TEXT,
                args       TEXT,
                env        TEXT,
                scope      TEXT NOT NULL DEFAULT 'global',
                product_id TEXT,
                enabled    INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_mcp_servers_scope
                ON mcp_servers(scope, product_id);

            CREATE TABLE IF NOT EXISTS product_autonomy (
                product_id     TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                action_type    TEXT NOT NULL,
                tier           TEXT NOT NULL DEFAULT 'approve',
                window_minutes INTEGER,
                PRIMARY KEY (product_id, action_type)
            );
            CREATE INDEX IF NOT EXISTS idx_product_autonomy_product
                ON product_autonomy(product_id);
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
        # Add new social_drafts columns (idempotent)
        _social_cols = [("image_url", "TEXT"), ("post_url", "TEXT")]
        for col_name, col_type in _social_cols:
            try:
                conn.execute(f"ALTER TABLE social_drafts ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass  # column already exists
        # Add autonomous workstream columns (idempotent)
        _ws_cols = [
            ("mission",     "TEXT NOT NULL DEFAULT ''"),
            ("schedule",    "TEXT NOT NULL DEFAULT 'manual'"),
            ("last_run_at", "TEXT"),
            ("next_run_at", "TEXT"),
        ]
        for col_name, col_type in _ws_cols:
            try:
                conn.execute(f"ALTER TABLE workstreams ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass  # column already exists
        # Add autonomous objective columns (idempotent)
        _obj_auto_cols = [
            ("autonomous",           "INTEGER NOT NULL DEFAULT 0"),
            ("session_id",           "TEXT"),
            ("next_run_at",          "TEXT"),
            ("last_run_at",          "TEXT"),
            ("blocked_by_review_id", "INTEGER"),
        ]
        for col_name, col_type in _obj_auto_cols:
            try:
                conn.execute(f"ALTER TABLE objectives ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass  # column already exists
        # Add launch wizard column to products (idempotent)
        try:
            conn.execute("ALTER TABLE products ADD COLUMN launch_wizard_active INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass  # column already exists

        # Add trust tier columns to products (idempotent)
        for col_name, col_def in [
            ("autonomy_master_tier",         "TEXT"),
            ("autonomy_master_window_minutes","INTEGER"),
        ]:
            try:
                conn.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass  # column already exists

        # Add trust tier columns to review_items (idempotent)
        for col_name, col_def in [
            ("action_type",    "TEXT"),
            ("auto_approve_at","DATETIME"),
        ]:
            try:
                conn.execute(f"ALTER TABLE review_items ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass  # column already exists

        # Add oauth_connections table (idempotent)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS oauth_connections (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id    TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                service       TEXT NOT NULL,
                email         TEXT NOT NULL,
                access_token  TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                token_expiry  TEXT,
                scopes        TEXT NOT NULL DEFAULT '',
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(product_id, service)
            )
        """)

        # Migrate: rename hannah_model key → agent_model (idempotent)
        conn.execute(
            "UPDATE model_config SET key = 'agent_model' WHERE key = 'hannah_model'"
        )
        # Seed agent_name default if missing (idempotent) — prefer AGENT_NAME env var
        _default_agent_name = os.environ.get("AGENT_NAME", "Adjutant")
        conn.execute(
            "INSERT INTO model_config (key, value, updated_at) "
            "VALUES ('agent_name', ?, datetime('now')) "
            "ON CONFLICT(key) DO NOTHING",
            (_default_agent_name,),
        )
        # On restart, mark any stale running events as done
        conn.execute(
            "UPDATE activity_events SET status = 'done' WHERE status = 'running'"
        )
        _seed_products(conn)

        # ── Sessions ──────────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                product_id TEXT REFERENCES products(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Recreate messages table with nullable product_id + session_id (idempotent)
        existing_cols = [
            r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()
        ]
        if "session_id" not in existing_cols:
            conn.executescript("""
                PRAGMA foreign_keys=OFF;
                CREATE TABLE messages_new (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT REFERENCES products(id),
                    session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
                    role       TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                INSERT INTO messages_new (id, product_id, role, content, created_at)
                    SELECT id, product_id, role, content, created_at FROM messages;
                DROP TABLE messages;
                ALTER TABLE messages_new RENAME TO messages;
                CREATE INDEX IF NOT EXISTS idx_messages_product
                    ON messages(product_id, id);
                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, id);
                PRAGMA foreign_keys=ON;
            """)

        # Recreate conversation_summaries with proper session-scoped schema
        cs_cols = [
            r[1] for r in conn.execute("PRAGMA table_info(conversation_summaries)").fetchall()
        ]
        if "session_id" not in cs_cols:
            conn.executescript("""
                PRAGMA foreign_keys=OFF;
                CREATE TABLE conversation_summaries_new (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT REFERENCES products(id) ON DELETE CASCADE,
                    session_id TEXT UNIQUE REFERENCES sessions(id) ON DELETE CASCADE,
                    summary    TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                INSERT INTO conversation_summaries_new (product_id, summary, updated_at)
                    SELECT product_id, summary, updated_at FROM conversation_summaries;
                DROP TABLE conversation_summaries;
                ALTER TABLE conversation_summaries_new RENAME TO conversation_summaries;
                CREATE UNIQUE INDEX IF NOT EXISTS idx_conv_summary_product_no_session
                    ON conversation_summaries(product_id) WHERE session_id IS NULL;
                PRAGMA foreign_keys=ON;
            """)

        # Migrate: create General sessions for products with un-assigned messages
        import uuid as _uuid
        products_with_msgs = conn.execute("""
            SELECT DISTINCT product_id FROM messages
            WHERE product_id IS NOT NULL AND session_id IS NULL
        """).fetchall()
        for (pid,) in products_with_msgs:
            existing_session = conn.execute(
                "SELECT id FROM sessions WHERE product_id = ? LIMIT 1", (pid,)
            ).fetchone()
            if existing_session:
                session_id = existing_session[0]
            else:
                session_id = _uuid.uuid4().hex[:16]
                conn.execute(
                    "INSERT INTO sessions (id, name, product_id) VALUES (?, 'General', ?)",
                    (session_id, pid),
                )
            conn.execute(
                "UPDATE messages SET session_id = ? WHERE product_id = ? AND session_id IS NULL",
                (session_id, pid),
            )


def _seed_products(conn: sqlite3.Connection) -> None:
    for p in get_seed_products():
        existing = conn.execute("SELECT id FROM products WHERE id = ?", (p["id"],)).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO products (id, name, icon_label, color) VALUES (?, ?, ?, ?)",
                (p["id"], p["name"], p["icon_label"], p["color"]),
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


def set_launch_wizard_active(product_id: str, active: bool) -> None:
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE products SET launch_wizard_active = ? WHERE id = ?",
            (1 if active else 0, product_id),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Product '{product_id}' not found")


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


def update_workstream_by_id(ws_id: int, name: str | None = None, status: str | None = None) -> None:
    sets, vals = [], []
    if name is not None:
        sets.append("name = ?"); vals.append(name)
    if status is not None:
        if status not in ("running", "warn", "paused"):
            raise ValueError(f"Invalid status: {status}")
        sets.append("status = ?"); vals.append(status)
    if not sets:
        return
    vals.append(ws_id)
    with _conn() as conn:
        conn.execute(f"UPDATE workstreams SET {', '.join(sets)} WHERE id = ?", vals)


def delete_workstream_by_id(ws_id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM workstreams WHERE id = ?", (ws_id,))


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
            """SELECT id, name, status, display_order,
                      mission, schedule, last_run_at, next_run_at
               FROM workstreams WHERE product_id = ? ORDER BY display_order""",
            (product_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_workstream_by_id(ws_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            """SELECT id, name, product_id, status, display_order,
                      mission, schedule, last_run_at, next_run_at
               FROM workstreams WHERE id = ?""",
            (ws_id,),
        ).fetchone()
    return dict(row) if row else None


def get_due_workstreams() -> list[dict]:
    """Return workstreams whose next_run_at has passed and are not paused."""
    from datetime import datetime
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        rows = conn.execute(
            """SELECT w.id, w.name, w.product_id, w.status,
                      w.mission, w.schedule, w.last_run_at, w.next_run_at
               FROM workstreams w
               WHERE w.next_run_at IS NOT NULL
                 AND w.next_run_at <= ?
                 AND w.status != 'paused'
                 AND w.mission != ''""",
            (now,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_workstream_fields(ws_id: int, **fields) -> None:
    """Flexible update for any workstream columns. Pass None to clear a nullable column."""
    _allowed = {"name", "status", "mission", "schedule", "last_run_at", "next_run_at"}
    updates = {k: v for k, v in fields.items() if k in _allowed}
    if not updates:
        return
    if "status" in updates and updates["status"] not in ("running", "warn", "paused", None):
        raise ValueError(f"Invalid status: {updates['status']}")
    sets = [f"{k} = ?" for k in updates]
    vals = list(updates.values()) + [ws_id]
    with _conn() as conn:
        conn.execute(f"UPDATE workstreams SET {', '.join(sets)} WHERE id = ?", vals)


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
            """SELECT id, text, progress_current, progress_target, display_order,
                      autonomous, session_id, next_run_at, last_run_at, blocked_by_review_id
               FROM objectives WHERE product_id = ? ORDER BY display_order""",
            (product_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_objective_by_id(
    obj_id: int,
    text: str | None = None,
    progress_current: int | None = None,
    progress_target: int | None = None,
) -> None:
    sets, vals = [], []
    if text is not None:
        sets.append("text = ?"); vals.append(text)
    if progress_current is not None:
        sets.append("progress_current = ?"); vals.append(progress_current)
    if progress_target is not None:
        sets.append("progress_target = ?"); vals.append(progress_target)
    if not sets:
        return
    vals.append(obj_id)
    with _conn() as conn:
        conn.execute(f"UPDATE objectives SET {', '.join(sets)} WHERE id = ?", vals)


def delete_objective_by_id(obj_id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM objectives WHERE id = ?", (obj_id,))


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


def get_objective_by_id(obj_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            """SELECT id, product_id, text, progress_current, progress_target, display_order,
                      autonomous, session_id, next_run_at, last_run_at, blocked_by_review_id
               FROM objectives WHERE id = ?""",
            (obj_id,),
        ).fetchone()
    return dict(row) if row else None


def set_objective_autonomous(obj_id: int, autonomous: bool) -> None:
    with _conn() as conn:
        if autonomous:
            conn.execute(
                "UPDATE objectives SET autonomous = 1, next_run_at = datetime('now') WHERE id = ?",
                (obj_id,),
            )
        else:
            conn.execute(
                "UPDATE objectives SET autonomous = 0, next_run_at = NULL, blocked_by_review_id = NULL WHERE id = ?",
                (obj_id,),
            )


def set_objective_session(obj_id: int, session_id: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE objectives SET session_id = ? WHERE id = ?",
            (session_id, obj_id),
        )


def set_objective_next_run(obj_id: int, hours: float) -> None:
    """Set next_run_at to now + hours (minimum 0.25h = 15 min). Updates last_run_at to now."""
    hours = max(0.25, float(hours))
    with _conn() as conn:
        conn.execute(
            "UPDATE objectives SET next_run_at = datetime('now', ? || ' hours'), last_run_at = datetime('now') WHERE id = ?",
            (f"+{hours}", obj_id),
        )


def set_objective_blocked(obj_id: int, review_item_id: int) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE objectives SET blocked_by_review_id = ?, next_run_at = NULL WHERE id = ?",
            (review_item_id, obj_id),
        )


def get_due_autonomous_objectives() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, product_id, text, progress_current, progress_target,
                      autonomous, session_id, next_run_at, last_run_at, blocked_by_review_id
               FROM objectives
               WHERE autonomous = 1
                 AND next_run_at IS NOT NULL
                 AND next_run_at <= datetime('now')
                 AND blocked_by_review_id IS NULL""",
        ).fetchall()
    return [dict(r) for r in rows]


def get_objective_blocked_by_review(review_item_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, product_id FROM objectives WHERE blocked_by_review_id = ?",
            (review_item_id,),
        ).fetchone()
    return dict(row) if row else None


def clear_objective_block(obj_id: int) -> None:
    """Clear blocked state and schedule immediate re-run."""
    with _conn() as conn:
        conn.execute(
            "UPDATE objectives SET blocked_by_review_id = NULL, next_run_at = datetime('now') WHERE id = ?",
            (obj_id,),
        )


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


def cancel_running_events(product_id: str) -> list[int]:
    """Mark all 'running' activity events for a product as 'done' (cancelled).
    Returns the list of affected event IDs so the caller can broadcast updates."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id FROM activity_events WHERE product_id = ? AND status = 'running'",
            (product_id,),
        ).fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            conn.execute(
                f"UPDATE activity_events SET status = 'done', summary = 'Cancelled.' WHERE id IN ({','.join('?' * len(ids))})",
                ids,
            )
    return ids


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
    action_type: Optional[str] = None,
) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO review_items
               (product_id, activity_event_id, title, description, risk_label, action_type)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (product_id, activity_event_id, title, description, risk_label, action_type),
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
            """SELECT id, activity_event_id, title, description, risk_label, status,
                      created_at, action_type, auto_approve_at
               FROM review_items WHERE product_id = ? AND status = ?
               ORDER BY created_at""",
            (product_id, status),
        ).fetchall()
    return [dict(r) for r in rows]


def set_auto_approve_at(item_id: int, dt: "datetime") -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE review_items SET auto_approve_at = ? WHERE id = ?",
            (dt.strftime("%Y-%m-%d %H:%M:%S"), item_id),
        )


def clear_auto_approve_at(item_id: int) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE review_items SET auto_approve_at = NULL WHERE id = ?",
            (item_id,),
        )


def auto_resolve_expired_reviews() -> list[dict]:
    """Find pending review items whose window has expired. Mark approved. Return {id, product_id} list."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, product_id FROM review_items
               WHERE status = 'pending'
               AND auto_approve_at IS NOT NULL
               AND auto_approve_at <= datetime('now')"""
        ).fetchall()
        if not rows:
            return []
        ids = [r[0] for r in rows]
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE review_items SET status = 'approved' WHERE id IN ({placeholders}) AND auto_approve_at IS NOT NULL AND status = 'pending'",
            ids,
        )
    return [{"id": r[0], "product_id": r[1]} for r in rows]


def get_autonomy_config(product_id: str, action_type: str) -> tuple[str, "int | None"]:
    """Resolve tier using: master → per-action → default('approve')."""
    with _conn() as conn:
        # Check master override first
        row = conn.execute(
            "SELECT autonomy_master_tier, autonomy_master_window_minutes FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if row and row["autonomy_master_tier"]:
            return row["autonomy_master_tier"], row["autonomy_master_window_minutes"]
        # Per-action row
        action_row = conn.execute(
            "SELECT tier, window_minutes FROM product_autonomy WHERE product_id = ? AND action_type = ?",
            (product_id, action_type),
        ).fetchone()
        if action_row:
            return action_row["tier"], action_row["window_minutes"]
    return "approve", None


def set_action_autonomy(
    product_id: str, action_type: str, tier: str, window_minutes: "int | None"
) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO product_autonomy (product_id, action_type, tier, window_minutes)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(product_id, action_type) DO UPDATE SET
                   tier = excluded.tier,
                   window_minutes = excluded.window_minutes""",
            (product_id, action_type, tier, window_minutes),
        )


def set_master_autonomy(
    product_id: str, tier: "str | None", window_minutes: "int | None"
) -> None:
    with _conn() as conn:
        conn.execute(
            """UPDATE products
               SET autonomy_master_tier = ?, autonomy_master_window_minutes = ?
               WHERE id = ?""",
            (tier, window_minutes, product_id),
        )


def get_product_autonomy_settings(product_id: str) -> dict:
    with _conn() as conn:
        row = conn.execute(
            "SELECT autonomy_master_tier, autonomy_master_window_minutes FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        action_rows = conn.execute(
            "SELECT action_type, tier, window_minutes FROM product_autonomy WHERE product_id = ? ORDER BY action_type",
            (product_id,),
        ).fetchall()
    return {
        "master_tier": row["autonomy_master_tier"] if row else None,
        "master_window_minutes": row["autonomy_master_window_minutes"] if row else None,
        "action_overrides": [dict(r) for r in action_rows],
    }


def get_review_item_by_id(item_id: int) -> "dict | None":
    with _conn() as conn:
        row = conn.execute(
            """SELECT id, product_id, activity_event_id, title, description, risk_label,
                      status, created_at, action_type, auto_approve_at
               FROM review_items WHERE id = ?""",
            (item_id,),
        ).fetchone()
    return dict(row) if row else None


def clear_product_autonomy(product_id: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM product_autonomy WHERE product_id = ?", (product_id,))


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(name: str, product_id: str | None = None) -> str:
    import uuid as _uuid
    session_id = _uuid.uuid4().hex[:16]
    with _conn() as conn:
        conn.execute(
            "INSERT INTO sessions (id, name, product_id) VALUES (?, ?, ?)",
            (session_id, name, product_id),
        )
    return session_id


def get_sessions(product_id: str | None) -> list[dict]:
    with _conn() as conn:
        if product_id is None:
            rows = conn.execute(
                "SELECT id, name, product_id, created_at FROM sessions "
                "WHERE product_id IS NULL ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, product_id, created_at FROM sessions "
                "WHERE product_id = ? ORDER BY created_at DESC",
                (product_id,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_first_session(product_id: str | None) -> dict | None:
    sessions = get_sessions(product_id)
    return sessions[0] if sessions else None


def rename_session(session_id: str, name: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE sessions SET name = ? WHERE id = ?", (name, session_id)
        )


def get_session_by_id(session_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, name, product_id, created_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_session(session_id: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


# ── Messages ──────────────────────────────────────────────────────────────────

def save_message(product_id: str | None, role: str, content, session_id: str | None = None) -> None:
    serialized = json.dumps(content) if not isinstance(content, str) else content
    with _conn() as conn:
        conn.execute(
            "INSERT INTO messages (product_id, session_id, role, content) VALUES (?, ?, ?, ?)",
            (product_id, session_id, role, serialized),
        )


def purge_broken_tool_exchanges(product_id: str) -> int:
    """Delete any assistant+tool_result pairs where tool_use lacks a matching result. Returns count deleted."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, role, content FROM messages WHERE product_id = ? ORDER BY id ASC",
            (product_id,),
        ).fetchall()

    bad_ids: list[int] = []
    parsed = []
    for r in rows:
        try:
            content = json.loads(r["content"])
        except Exception:
            content = r["content"]
        parsed.append({"id": r["id"], "role": r["role"], "content": content})

    for i, msg in enumerate(parsed):
        if msg["role"] != "assistant":
            continue
        content = msg["content"]
        if not isinstance(content, list):
            continue
        tool_ids = {b["id"] for b in content if isinstance(b, dict) and b.get("type") == "tool_use"}
        if not tool_ids:
            continue
        next_i = i + 1
        next_content = parsed[next_i]["content"] if next_i < len(parsed) else ""
        result_ids: set = set()
        if isinstance(next_content, list):
            result_ids = {b.get("tool_use_id") for b in next_content
                          if isinstance(b, dict) and b.get("type") == "tool_result"}
        if not tool_ids.issubset(result_ids):
            bad_ids.append(msg["id"])
            if next_i < len(parsed):
                bad_ids.append(parsed[next_i]["id"])

    if bad_ids:
        delete_messages_by_ids(product_id, bad_ids)
    return len(bad_ids)


def load_messages(product_id: str | None, session_id: str | None = None, limit: int = 15) -> list[dict]:
    with _conn() as conn:
        if session_id is not None:
            rows = conn.execute(
                "SELECT role, content, created_at FROM messages "
                "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        elif product_id is not None:
            # Fallback: load by product_id (legacy or pre-sessions)
            rows = conn.execute(
                "SELECT role, content, created_at FROM messages "
                "WHERE product_id = ? ORDER BY id DESC LIMIT ?",
                (product_id, limit),
            ).fetchall()
        else:
            rows = []
    result = []
    for r in reversed(rows):
        try:
            content = json.loads(r["content"])
        except (json.JSONDecodeError, TypeError):
            content = r["content"]
        result.append({"role": r["role"], "content": content, "ts": r["created_at"]})
    return result


def get_messages_for_summary(product_id: str, max_id: int) -> list[dict]:
    """Return all messages with id <= max_id for summarization."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE product_id = ? AND id <= ? ORDER BY id ASC",
            (product_id, max_id),
        ).fetchall()
    result = []
    for r in rows:
        try:
            content = json.loads(r["content"])
        except (json.JSONDecodeError, TypeError):
            content = r["content"]
        result.append({"role": r["role"], "content": content})
    return result


def count_messages(product_id: str) -> int:
    with _conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM messages WHERE product_id = ?", (product_id,)
        ).fetchone()[0]


def get_oldest_message_ids(product_id: str, n: int) -> list[int]:
    """Return IDs of the n oldest messages for a product."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id FROM messages WHERE product_id = ? ORDER BY id ASC LIMIT ?",
            (product_id, n),
        ).fetchall()
    return [r[0] for r in rows]


def delete_messages_by_ids(product_id: str, ids: list[int]) -> None:
    if not ids:
        return
    placeholders = ",".join("?" * len(ids))
    with _conn() as conn:
        conn.execute(
            f"DELETE FROM messages WHERE product_id = ? AND id IN ({placeholders})",
            [product_id, *ids],
        )


def get_conversation_summary(product_id: str, session_id: str | None = None) -> str:
    with _conn() as conn:
        if session_id:
            row = conn.execute(
                "SELECT summary FROM conversation_summaries WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT summary FROM conversation_summaries WHERE product_id = ? AND session_id IS NULL",
                (product_id,),
            ).fetchone()
    return row["summary"] if row else ""


def save_conversation_summary(product_id: str, summary: str, session_id: str | None = None) -> None:
    with _conn() as conn:
        if session_id:
            conn.execute(
                """INSERT INTO conversation_summaries (product_id, session_id, summary, updated_at)
                   VALUES (?, ?, ?, datetime('now'))
                   ON CONFLICT(session_id) DO UPDATE SET
                       summary=excluded.summary, updated_at=excluded.updated_at""",
                (product_id, session_id, summary),
            )
        else:
            conn.execute(
                """INSERT INTO conversation_summaries (product_id, summary, updated_at)
                   VALUES (?, ?, datetime('now'))
                   ON CONFLICT(product_id) WHERE session_id IS NULL DO UPDATE SET
                       summary=excluded.summary, updated_at=excluded.updated_at""",
                (product_id, summary),
            )


# ── Social drafts ─────────────────────────────────────────────────────────────

def save_social_draft(
    product_id: str,
    platform: str,
    content: str,
    image_description: str = "",
    image_url: str = "",
    review_item_id: int | None = None,
) -> int:
    with _conn() as conn:
        cursor = conn.execute(
            "INSERT INTO social_drafts (product_id, platform, content, image_description, image_url, review_item_id) VALUES (?, ?, ?, ?, ?, ?)",
            (product_id, platform, content, image_description, image_url, review_item_id),
        )
    return cursor.lastrowid


def get_social_draft_by_review_item(review_item_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM social_drafts WHERE review_item_id = ? LIMIT 1",
            (review_item_id,),
        ).fetchone()
    return dict(row) if row else None


def update_social_draft_status(draft_id: int, status: str, post_url: str | None = None) -> None:
    with _conn() as conn:
        if post_url:
            conn.execute(
                "UPDATE social_drafts SET status = ?, post_url = ? WHERE id = ?",
                (status, post_url, draft_id),
            )
        else:
            conn.execute(
                "UPDATE social_drafts SET status = ? WHERE id = ?",
                (status, draft_id),
            )


def list_social_drafts(product_id: str, status: str = "pending_review") -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM social_drafts WHERE product_id = ? AND status = ? ORDER BY created_at DESC",
            (product_id, status),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Directive templates ───────────────────────────────────────────────────────

def get_directive_templates(product_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, label, content, display_order FROM directive_templates WHERE product_id = ? ORDER BY display_order, id",
            (product_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_directive_template(product_id: str, label: str, content: str) -> dict:
    with _conn() as conn:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(display_order), -1) FROM directive_templates WHERE product_id = ?",
            (product_id,),
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO directive_templates (product_id, label, content, display_order) VALUES (?, ?, ?, ?)",
            (product_id, label, content, max_order + 1),
        )
        row = conn.execute(
            "SELECT id, label, content, display_order FROM directive_templates WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return dict(row)


def update_directive_template(template_id: int, label: str, content: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE directive_templates SET label = ?, content = ? WHERE id = ?",
            (label, content, template_id),
        )


def delete_directive_template(template_id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM directive_templates WHERE id = ?", (template_id,))


# ── Agent / Model config ──────────────────────────────────────────────────────

_AGENT_CONFIG_DEFAULTS = {
    "agent_model":    "claude-sonnet-4-6",
    "subagent_model": "claude-sonnet-4-6",
    "agent_name":     os.environ.get("AGENT_NAME", "Adjutant"),
}

def get_agent_config() -> dict:
    with _conn() as conn:
        rows = conn.execute("SELECT key, value FROM model_config").fetchall()
    result = dict(_AGENT_CONFIG_DEFAULTS)
    for r in rows:
        result[r["key"]] = r["value"]
    return result

def set_agent_config(key: str, value: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO model_config (key, value, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, value),
        )

# ── Notes ─────────────────────────────────────────────────────────────────────

def get_notes(product_id: str) -> dict:
    with _conn() as conn:
        row = conn.execute(
            "SELECT content, updated_at FROM product_notes WHERE product_id = ?",
            (product_id,),
        ).fetchone()
    if row:
        return dict(row)
    return {"content": "", "updated_at": ""}


def set_notes(product_id: str, content: str) -> dict:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO product_notes (product_id, content, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(product_id) DO UPDATE SET
                   content    = excluded.content,
                   updated_at = excluded.updated_at""",
            (product_id, content),
        )
        row = conn.execute(
            "SELECT content, updated_at FROM product_notes WHERE product_id = ?",
            (product_id,),
        ).fetchone()
    return dict(row)


# ── Directive history ─────────────────────────────────────────────────────────

def save_directive_history(product_id: str, content: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO directive_history (product_id, content) VALUES (?, ?)",
            (product_id, content),
        )


def get_directive_history(product_id: str, limit: int = 20) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, content, created_at
               FROM directive_history
               WHERE product_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (product_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Overview ──────────────────────────────────────────────────────────────────

def get_overview() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT
                   p.id, p.name, p.icon_label, p.color,
                   COALESCE(SUM(CASE WHEN w.status='running' THEN 1 ELSE 0 END), 0) AS running_ws,
                   COALESCE(SUM(CASE WHEN w.status='warn'    THEN 1 ELSE 0 END), 0) AS warn_ws,
                   COALESCE(SUM(CASE WHEN w.status='paused'  THEN 1 ELSE 0 END), 0) AS paused_ws,
                   (SELECT COUNT(*) FROM review_items r
                    WHERE r.product_id = p.id AND r.status = 'pending') AS pending_reviews,
                   (SELECT COUNT(*) FROM activity_events ae
                    WHERE ae.product_id = p.id AND ae.status = 'running') AS running_agents
               FROM products p
               LEFT JOIN workstreams w ON w.product_id = p.id
               GROUP BY p.id
               ORDER BY p.name"""
        ).fetchall()
    return [dict(r) for r in rows]


# ── Digest ────────────────────────────────────────────────────────────────────

def get_digest_data() -> dict:
    """Compile cross-product activity data for the email digest."""
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        products = conn.execute(
            "SELECT id, name FROM products ORDER BY name"
        ).fetchall()
        result = []
        for p in products:
            pid = p["id"]
            workstreams = conn.execute(
                """SELECT name, status, schedule, last_run_at
                   FROM workstreams WHERE product_id = ? ORDER BY display_order""",
                (pid,),
            ).fetchall()
            recent_events = conn.execute(
                """SELECT headline, status, summary
                   FROM activity_events
                   WHERE product_id = ? AND created_at >= ?
                   ORDER BY created_at DESC LIMIT 10""",
                (pid, cutoff),
            ).fetchall()
            pending_reviews = conn.execute(
                """SELECT title, risk_label
                   FROM review_items WHERE product_id = ? AND status = 'pending'""",
                (pid,),
            ).fetchall()
            result.append({
                "product_name":    p["name"],
                "workstreams":     [dict(w) for w in workstreams],
                "recent_events":   [dict(e) for e in recent_events],
                "pending_reviews": [dict(r) for r in pending_reviews],
            })
    return {
        "products":     result,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ── MCP Servers ───────────────────────────────────────────────────────────────

def add_mcp_server(
    name: str,
    type: str,
    url: str | None,
    command: str | None,
    args: str | None,
    env: str | None,
    scope: str,
    product_id: str | None,
) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO mcp_servers (name, type, url, command, args, env, scope, product_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, type, url, command, args, env, scope, product_id),
        )
        return cur.lastrowid


def list_mcp_servers(product_id: str) -> list[dict]:
    """Return all MCP servers for a product: globals + product-scoped."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT * FROM mcp_servers
               WHERE scope = 'global'
               OR (scope = 'product' AND product_id = ?)
               ORDER BY scope DESC, id ASC""",
            (product_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_all_mcp_servers() -> list[dict]:
    """Return every MCP server regardless of scope (used by Settings UI)."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM mcp_servers ORDER BY scope DESC, id ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_mcp_server(id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM mcp_servers WHERE id = ?", (id,)
        ).fetchone()
        return dict(row) if row else None


def update_mcp_server(id: int, enabled: bool) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE mcp_servers SET enabled = ? WHERE id = ?", (int(enabled), id)
        )


# ── OAuth connections ─────────────────────────────────────────────────────────

def save_oauth_connection(
    product_id: str,
    service: str,
    email: str,
    access_token: str,
    refresh_token: str,
    token_expiry: str,
    scopes: str,
) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO oauth_connections
               (product_id, service, email, access_token, refresh_token, token_expiry, scopes, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(product_id, service) DO UPDATE SET
                   email=excluded.email, access_token=excluded.access_token,
                   refresh_token=excluded.refresh_token, token_expiry=excluded.token_expiry,
                   scopes=excluded.scopes, updated_at=excluded.updated_at""",
            (product_id, service, email, access_token, refresh_token, token_expiry, scopes),
        )


def get_oauth_connection(product_id: str, service: str) -> "dict | None":
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM oauth_connections WHERE product_id=? AND service=?",
            (product_id, service),
        ).fetchone()
    return dict(row) if row else None


def delete_oauth_connection(product_id: str, service: str) -> None:
    with _conn() as conn:
        conn.execute(
            "DELETE FROM oauth_connections WHERE product_id=? AND service=?",
            (product_id, service),
        )


def list_oauth_connections(product_id: str) -> list:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT service, email, scopes, updated_at FROM oauth_connections WHERE product_id=?",
            (product_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_mcp_server(id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM mcp_servers WHERE id = ?", (id,))
