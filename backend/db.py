# backend/db.py
"""SQLite persistence — multi-product schema with WAL mode."""

import json
import logging
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
                product_id     TEXT REFERENCES products(id) ON DELETE CASCADE,
                agent_type     TEXT NOT NULL DEFAULT 'general',
                headline       TEXT NOT NULL DEFAULT '',
                rationale      TEXT NOT NULL DEFAULT '',
                status         TEXT NOT NULL DEFAULT 'running',
                output_preview TEXT,
                summary        TEXT,
                created_at     TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS review_items (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id        TEXT REFERENCES products(id),
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
                scheduled_for     TEXT,
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

            CREATE TABLE IF NOT EXISTS mcp_capability_overrides (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id      TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                capability_slot TEXT NOT NULL,
                mcp_server_name TEXT NOT NULL,
                mcp_tool_names  TEXT NOT NULL DEFAULT '[]',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(product_id, capability_slot)
            );

            CREATE TABLE IF NOT EXISTS capability_slot_definitions (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL UNIQUE,
                label          TEXT NOT NULL,
                built_in_tools TEXT NOT NULL DEFAULT '[]',
                is_system      INTEGER NOT NULL DEFAULT 0,
                created_at     TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS extension_permissions (
                extension_name TEXT NOT NULL,
                scope          TEXT NOT NULL DEFAULT 'global',
                product_id     TEXT NOT NULL DEFAULT '',
                enabled        INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (extension_name, product_id)
            );

            CREATE TABLE IF NOT EXISTS token_usage (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id            TEXT,
                call_type             TEXT    NOT NULL,
                provider              TEXT    NOT NULL DEFAULT 'anthropic',
                model                 TEXT    NOT NULL,
                input_tokens          INTEGER NOT NULL DEFAULT 0,
                output_tokens         INTEGER NOT NULL DEFAULT 0,
                cache_read_tokens     INTEGER NOT NULL DEFAULT 0,
                cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
                created_at            TEXT    NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_token_usage_created_at
                ON token_usage(created_at);

            CREATE TABLE IF NOT EXISTS run_reports (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id       TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                workstream_id    INTEGER NOT NULL,  -- snapshot ref, no FK (survives workstream deletion)
                workstream_name  TEXT NOT NULL,
                full_output      TEXT NOT NULL DEFAULT '',
                created_at       TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_run_reports_product
                ON run_reports(product_id, created_at DESC);
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
        _social_cols = [("image_url", "TEXT"), ("post_url", "TEXT"), ("scheduled_for", "TEXT")]
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

        # Add per-product model override columns (idempotent)
        for col_name in ("agent_model", "subagent_model", "prescreener_model"):
            try:
                conn.execute(f"ALTER TABLE products ADD COLUMN {col_name} TEXT")
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

        # Add report_id to activity_events (idempotent)
        try:
            conn.execute("ALTER TABLE activity_events ADD COLUMN report_id INTEGER")
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

        # Add browser_credentials table (idempotent)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS browser_credentials (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                service     TEXT NOT NULL,
                username    TEXT NOT NULL DEFAULT '',
                password    TEXT NOT NULL DEFAULT '',
                handle      TEXT NOT NULL DEFAULT '',
                active      INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(product_id, service)
            )
        """)
        try:
            conn.execute("ALTER TABLE browser_credentials ADD COLUMN handle TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass  # column already exists

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
        _seed_capability_slots(conn)

    migrate_extensions_to_db()
    migrate_capability_overrides_to_tool_names()

    with _conn() as conn:
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

        # Migrate: make activity_events.product_id nullable so global (product_id=None) tasks work
        ae_cols = {r[1]: r[3] for r in conn.execute("PRAGMA table_info(activity_events)").fetchall()}
        if ae_cols.get("product_id") == 1:  # 1 = NOT NULL
            conn.executescript("""
                PRAGMA foreign_keys=OFF;
                DROP TABLE IF EXISTS activity_events_new;
                CREATE TABLE activity_events_new (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id     TEXT REFERENCES products(id) ON DELETE CASCADE,
                    agent_type     TEXT NOT NULL DEFAULT 'general',
                    headline       TEXT NOT NULL DEFAULT '',
                    rationale      TEXT NOT NULL DEFAULT '',
                    status         TEXT NOT NULL DEFAULT 'running',
                    summary        TEXT,
                    output_preview TEXT,
                    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
                );
                INSERT INTO activity_events_new
                    (id, product_id, agent_type, headline, rationale,
                     status, summary, output_preview, created_at)
                    SELECT id, product_id, agent_type, headline, rationale,
                           status, summary, output_preview, created_at
                    FROM activity_events;
                DROP TABLE activity_events;
                ALTER TABLE activity_events_new RENAME TO activity_events;
                CREATE INDEX IF NOT EXISTS idx_activity_events_product
                    ON activity_events(product_id, created_at);
                PRAGMA foreign_keys=ON;
            """)

        # Migrate: make review_items.product_id nullable so global tasks work
        ri_cols = {r[1]: r[3] for r in conn.execute("PRAGMA table_info(review_items)").fetchall()}
        if ri_cols.get("product_id") == 1:  # 1 = NOT NULL
            conn.executescript("""
                PRAGMA foreign_keys=OFF;
                DROP TABLE IF EXISTS review_items_new;
                CREATE TABLE review_items_new (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id        TEXT REFERENCES products(id),
                    activity_event_id INTEGER REFERENCES activity_events(id),
                    title             TEXT NOT NULL,
                    description       TEXT NOT NULL,
                    risk_label        TEXT NOT NULL,
                    status            TEXT NOT NULL DEFAULT 'pending',
                    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
                    action_type       TEXT,
                    auto_approve_at   DATETIME
                );
                INSERT INTO review_items_new
                    (id, product_id, activity_event_id, title, description,
                     risk_label, status, created_at)
                    SELECT id, product_id, activity_event_id, title, description,
                           risk_label, status, created_at
                    FROM review_items;
                DROP TABLE review_items;
                ALTER TABLE review_items_new RENAME TO review_items;
                CREATE INDEX IF NOT EXISTS idx_review_items_product
                    ON review_items(product_id, status);
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


_SYSTEM_SLOTS = [
    ("social_post", "Social Posting", ["post_to_social", "draft_social_post"]),
    ("email_send",  "Email Sending",  ["send_email", "draft_email"]),
]


def _seed_capability_slots(conn: sqlite3.Connection) -> None:
    for name, label, tools in _SYSTEM_SLOTS:
        conn.execute(
            """INSERT OR IGNORE INTO capability_slot_definitions (name, label, built_in_tools, is_system)
               VALUES (?, ?, ?, 1)""",
            (name, label, json.dumps(tools)),
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
        # Delete child records first (non-cascade FKs must be cleared before the product row)
        for table in (
            "messages", "review_items", "activity_events", "social_drafts",
            "objectives", "workstreams", "sessions",
            "conversation_summaries", "directive_templates",
            "product_notes", "directive_history",
        ):
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
    autonomous: int | None = None,
) -> None:
    sets, vals = [], []
    if text is not None:
        sets.append("text = ?"); vals.append(text)
    if progress_current is not None:
        sets.append("progress_current = ?"); vals.append(progress_current)
    if progress_target is not None:
        sets.append("progress_target = ?"); vals.append(progress_target)
    if autonomous is not None:
        sets.append("autonomous = ?"); vals.append(autonomous)
        # When enabling autonomous mode, schedule an immediate run; when disabling, clear schedule
        if autonomous == 1:
            sets.append("next_run_at = datetime('now')")
        else:
            sets.append("next_run_at = NULL")
            sets.append("blocked_by_review_id = NULL")
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
    report_id: Optional[int] = None,
) -> None:
    with _conn() as conn:
        conn.execute(
            """UPDATE activity_events
               SET status = ?, summary = ?,
                   output_preview = COALESCE(?, output_preview),
                   report_id = COALESCE(?, report_id)
               WHERE id = ?""",
            (status, summary, output_preview, report_id, event_id),
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
            """SELECT id, agent_type, headline, rationale, status,
                      output_preview, summary, report_id, created_at
               FROM activity_events WHERE product_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (product_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


# ── Run reports ───────────────────────────────────────────────────────────────

def create_run_report(
    product_id: str,
    workstream_id: int,
    workstream_name: str,
    full_output: str,
) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO run_reports (product_id, workstream_id, workstream_name, full_output)
               VALUES (?, ?, ?, ?)""",
            (product_id, workstream_id, workstream_name, full_output),
        )
        return cur.lastrowid


def get_run_reports(product_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, workstream_id, workstream_name, full_output, created_at
               FROM run_reports WHERE product_id = ?
               ORDER BY created_at DESC, id DESC""",
            (product_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_run_report(report_id: int) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, product_id, workstream_id, workstream_name, full_output, created_at FROM run_reports WHERE id = ?",
            (report_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_run_report(report_id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM run_reports WHERE id = ?", (report_id,))


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
            """SELECT ri.id, ri.activity_event_id, ri.title, ri.description, ri.risk_label,
                      ri.status, ri.created_at, ri.action_type, ri.auto_approve_at,
                      sd.scheduled_for
               FROM review_items ri
               LEFT JOIN social_drafts sd ON sd.review_item_id = ri.id
               WHERE ri.product_id = ? AND ri.status = ?
               ORDER BY ri.created_at""",
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
    scheduled_for: str | None = None,
) -> int:
    with _conn() as conn:
        cursor = conn.execute(
            "INSERT INTO social_drafts (product_id, platform, content, image_description, image_url, review_item_id, scheduled_for) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (product_id, platform, content, image_description, image_url, review_item_id, scheduled_for),
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


def get_due_scheduled_drafts() -> list[dict]:
    """Return all social drafts with status='scheduled' whose scheduled_for <= now."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT * FROM social_drafts
               WHERE status = 'scheduled'
                 AND scheduled_for IS NOT NULL
                 AND scheduled_for <= datetime('now')
               ORDER BY scheduled_for""",
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
    "agent_model":                "claude-sonnet-4-6",
    "subagent_model":             "claude-sonnet-4-6",
    "prescreener_model":          "claude-haiku-4-5-20251001",
    "agent_name":                 os.environ.get("AGENT_NAME", "Adjutant"),
    "google_oauth_client_id":     "",
    "google_oauth_client_secret": "",
    "twitter_client_id":          "",
    "twitter_client_secret":      "",
    "linkedin_client_id":         "",
    "linkedin_client_secret":     "",
    "meta_app_id":                "",
    "meta_app_secret":            "",
    "anthropic_api_key":          "",
    "openai_api_key":             "",
    "available_models_cache":     "",
    "available_models_cache_updated_at": "",
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

def get_product_model_config(product_id: str | None) -> dict:
    """Return resolved {agent_model, subagent_model, prescreener_model} for a product.
    Per-product values override global model_config defaults."""
    global_cfg = get_agent_config()
    defaults = {
        "agent_model":       global_cfg["agent_model"],
        "subagent_model":    global_cfg["subagent_model"],
        "prescreener_model": global_cfg["prescreener_model"],
    }
    if not product_id:
        return defaults
    with _conn() as conn:
        row = conn.execute(
            "SELECT agent_model, subagent_model, prescreener_model FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
    if not row:
        return defaults
    return {
        "agent_model":       row["agent_model"]       or defaults["agent_model"],
        "subagent_model":    row["subagent_model"]    or defaults["subagent_model"],
        "prescreener_model": row["prescreener_model"] or defaults["prescreener_model"],
    }


def set_product_model_config(
    product_id: str,
    agent_model: str | None = ...,
    subagent_model: str | None = ...,
    prescreener_model: str | None = ...,
) -> None:
    """Write per-product model overrides. Pass None to clear (revert to global default).
    Omit a parameter entirely to leave it unchanged (uses sentinel ... default)."""
    updates: dict[str, str | None] = {}
    if agent_model is not ...:
        updates["agent_model"] = agent_model or None
    if subagent_model is not ...:
        updates["subagent_model"] = subagent_model or None
    if prescreener_model is not ...:
        updates["prescreener_model"] = prescreener_model or None
    if not updates:
        return
    sets = ", ".join(f"{k} = ?" for k in updates)
    with _conn() as conn:
        conn.execute(
            f"UPDATE products SET {sets} WHERE id = ?",
            (*updates.values(), product_id),
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


def get_mcp_server_by_name(name: str) -> dict | None:
    """Return the first MCP server row matching the given name, or None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, name, type, url, env FROM mcp_servers WHERE name = ? LIMIT 1",
            (name,),
        ).fetchone()
        return dict(row) if row else None


def list_all_extensions_with_permissions() -> list[dict]:
    """Return all rows from extension_permissions."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT extension_name, scope, product_id, enabled FROM extension_permissions"
        ).fetchall()
        return [dict(r) for r in rows]


def get_product_extension_names(product_id: str) -> set[str]:
    """Return names of extensions enabled for a product (global + product-scoped)."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT extension_name FROM extension_permissions
               WHERE enabled = 1
                 AND (scope = 'global' OR (scope = 'product' AND product_id = ?))""",
            (product_id,),
        ).fetchall()
        return {r["extension_name"] for r in rows}


def add_extension_permission(name: str, scope: str, product_id: str = "", enabled: int = 1) -> None:
    """Insert or replace an extension permission row."""
    with _conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO extension_permissions
               (extension_name, scope, product_id, enabled) VALUES (?, ?, ?, ?)""",
            (name, scope, product_id, enabled),
        )


def set_extension_enabled(name: str, product_id: str, enabled: bool) -> None:
    """Toggle the enabled flag for a specific (extension_name, product_id) row.

    No-op if the row does not exist (caller is responsible for prior insert).
    """
    with _conn() as conn:
        conn.execute(
            """UPDATE extension_permissions SET enabled = ?
               WHERE extension_name = ? AND product_id = ?""",
            (1 if enabled else 0, name, product_id),
        )


def set_extension_scope(name: str, scope: str, new_product_id: str = "") -> None:
    """Change scope and product_id for an extension. Assumes one row per extension name.

    Deletes the old row and inserts a new one to update the PRIMARY KEY columns,
    preserving the enabled state.
    """
    with _conn() as conn:
        row = conn.execute(
            "SELECT enabled FROM extension_permissions WHERE extension_name = ? LIMIT 1",
            (name,),
        ).fetchone()
        enabled = row["enabled"] if row else 1
        conn.execute("DELETE FROM extension_permissions WHERE extension_name = ?", (name,))
        conn.execute(
            """INSERT INTO extension_permissions (extension_name, scope, product_id, enabled)
               VALUES (?, ?, ?, ?)""",
            (name, scope, new_product_id, enabled),
        )


def delete_extension_permission(name: str) -> None:
    """Remove all permission rows for an extension (called when extension is deleted)."""
    with _conn() as conn:
        conn.execute("DELETE FROM extension_permissions WHERE extension_name = ?", (name,))


def migrate_extensions_to_db() -> None:
    """Seed extension_permissions from extensions/_config.json if table is empty.

    Called once at startup. After migration, extension_permissions is the source
    of truth; _config.json is no longer written to by the new code paths.
    """
    import pkgutil
    from pathlib import Path
    ext_dir = Path(__file__).parent.parent / "extensions"
    if not ext_dir.exists():
        return

    config_file = ext_dir / "_config.json"
    disabled: set[str] = set()
    if config_file.exists():
        try:
            disabled = set(json.loads(config_file.read_text()).get("disabled", []))
        except Exception:
            pass

    with _conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM extension_permissions").fetchone()[0]
        if count > 0:
            return
        for _, name, _ in pkgutil.iter_modules([str(ext_dir)]):
            enabled = 0 if name in disabled else 1
            conn.execute(
                """INSERT OR IGNORE INTO extension_permissions
                   (extension_name, scope, product_id, enabled) VALUES (?, 'global', '', ?)""",
                (name, enabled),
            )


def migrate_capability_overrides_to_tool_names() -> None:
    """Convert mcp_capability_overrides.mcp_tool_name (str) → mcp_tool_names (JSON array).

    Safe to call on already-migrated databases — the column-existence guard exits early.
    """
    with _conn() as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(mcp_capability_overrides)").fetchall()]
        if "mcp_tool_names" in cols:
            return
        conn.executescript("""
            PRAGMA foreign_keys=OFF;
            CREATE TABLE mcp_capability_overrides_new (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id      TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                capability_slot TEXT NOT NULL,
                mcp_server_name TEXT NOT NULL,
                mcp_tool_names  TEXT NOT NULL DEFAULT '[]',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(product_id, capability_slot)
            );
            INSERT INTO mcp_capability_overrides_new
                (id, product_id, capability_slot, mcp_server_name, mcp_tool_names, created_at)
            SELECT id, product_id, capability_slot, mcp_server_name,
                   json_array(mcp_tool_name), created_at
            FROM mcp_capability_overrides;
            DROP TABLE mcp_capability_overrides;
            ALTER TABLE mcp_capability_overrides_new RENAME TO mcp_capability_overrides;
            PRAGMA foreign_keys=ON;
        """)


def update_mcp_server(
    id: int,
    enabled: bool | None = None,
    name: str | None = None,
    url: str | None = None,
    command: str | None = None,
    args: str | None = None,
    env: str | None = None,
) -> None:
    fields, values = [], []
    if enabled is not None:
        fields.append("enabled = ?"); values.append(int(enabled))
    if name is not None:
        fields.append("name = ?"); values.append(name)
    if url is not None:
        fields.append("url = ?"); values.append(url)
    if command is not None:
        fields.append("command = ?"); values.append(command)
    if args is not None:
        fields.append("args = ?"); values.append(args)
    if env is not None:
        fields.append("env = ?"); values.append(env)
    if not fields:
        return
    values.append(id)
    with _conn() as conn:
        conn.execute(f"UPDATE mcp_servers SET {', '.join(fields)} WHERE id = ?", values)


# ── OAuth connections ─────────────────────────────────────────────────────────

def save_oauth_connection(
    product_id: str,
    service: str,
    email: str,
    access_token: str,
    refresh_token: str,
    token_expiry: str | None,
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


def get_oauth_connection(product_id: str, service: str) -> dict | None:
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


def list_oauth_connections(product_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT service, email, scopes, updated_at FROM oauth_connections WHERE product_id=?",
            (product_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def save_browser_credential(
    product_id: str,
    service: str,
    username: str,
    password: str,
    active: bool,
    handle: str = "",
) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO browser_credentials (product_id, service, username, password, handle, active)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(product_id, service) DO UPDATE SET
                   username=excluded.username,
                   password=excluded.password,
                   handle=excluded.handle,
                   active=excluded.active""",
            (product_id, service, username, password, handle, 1 if active else 0),
        )


def get_browser_credential(product_id: str, service: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM browser_credentials WHERE product_id = ? AND service = ?",
            (product_id, service),
        ).fetchone()
    return dict(row) if row else None


def delete_browser_credential(product_id: str, service: str) -> None:
    with _conn() as conn:
        conn.execute(
            "DELETE FROM browser_credentials WHERE product_id = ? AND service = ?",
            (product_id, service),
        )


def list_browser_credentials(product_id: str) -> list[dict]:
    """Returns service, username, handle, active — never password."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT service, username, handle, active FROM browser_credentials WHERE product_id = ?",
            (product_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_mcp_server(id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM mcp_servers WHERE id = ?", (id,))


def list_capability_overrides(product_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT capability_slot, mcp_server_name, mcp_tool_names FROM mcp_capability_overrides WHERE product_id = ?",
            (product_id,),
        ).fetchall()
    return [
        {**dict(r), "mcp_tool_names": json.loads(r["mcp_tool_names"])}
        for r in rows
    ]


def set_capability_override(
    product_id: str, capability_slot: str, mcp_server_name: str, mcp_tool_names: list[str],
) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO mcp_capability_overrides (product_id, capability_slot, mcp_server_name, mcp_tool_names)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(product_id, capability_slot) DO UPDATE SET
                 mcp_server_name = excluded.mcp_server_name,
                 mcp_tool_names  = excluded.mcp_tool_names""",
            (product_id, capability_slot, mcp_server_name, json.dumps(mcp_tool_names)),
        )


def delete_capability_override(product_id: str, capability_slot: str) -> None:
    with _conn() as conn:
        conn.execute(
            "DELETE FROM mcp_capability_overrides WHERE product_id = ? AND capability_slot = ?",
            (product_id, capability_slot),
        )


# ── Capability Slot Definitions ───────────────────────────────────────────────

def list_capability_slot_definitions() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT name, label, built_in_tools, is_system FROM capability_slot_definitions ORDER BY id"
        ).fetchall()
    return [
        {**dict(r), "built_in_tools": json.loads(r["built_in_tools"])}
        for r in rows
    ]


def create_capability_slot_definition(name: str, label: str, built_in_tools: list[str]) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO capability_slot_definitions (name, label, built_in_tools, is_system) VALUES (?, ?, ?, 0)",
            (name, label, json.dumps(built_in_tools)),
        )


def delete_capability_slot_definition(name: str) -> None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT is_system FROM capability_slot_definitions WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Capability slot '{name}' not found.")
        if row["is_system"]:
            raise ValueError(f"Cannot delete system slot '{name}'.")
        conn.execute("DELETE FROM mcp_capability_overrides WHERE capability_slot = ?", (name,))
        conn.execute("DELETE FROM capability_slot_definitions WHERE name = ?", (name,))


# ── Token usage tracking ──────────────────────────────────────────────────────

def _normalize_usage(provider: str, usage) -> dict:
    """Translate provider-specific usage object into a common field dict."""
    try:
        if provider == "anthropic":
            return {
                "input_tokens":          getattr(usage, "input_tokens", 0) or 0,
                "output_tokens":         getattr(usage, "output_tokens", 0) or 0,
                "cache_read_tokens":     getattr(usage, "cache_read_input_tokens", 0) or 0,
                "cache_creation_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
            }
        if provider == "openai":
            details = getattr(usage, "prompt_tokens_details", None)
            cached = 0
            if details is not None:
                cached = getattr(details, "cached_tokens", None)
                if cached is None:
                    cached = details.get("cached_tokens", 0) if isinstance(details, dict) else 0
                cached = cached or 0
            return {
                "input_tokens":          getattr(usage, "prompt_tokens", 0) or 0,
                "output_tokens":         getattr(usage, "completion_tokens", 0) or 0,
                "cache_read_tokens":     cached,
                "cache_creation_tokens": 0,
            }
    except Exception:
        pass
    return {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0}


def record_token_usage(
    product_id: str | None,
    call_type: str,
    provider: str,
    model: str,
    usage,
) -> None:
    """Normalise and insert one usage row. Never raises — a failed write must not break an agent turn."""
    try:
        fields = _normalize_usage(provider, usage)
        with _conn() as conn:
            conn.execute(
                """INSERT INTO token_usage
                   (product_id, call_type, provider, model,
                    input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (product_id, call_type, provider, model,
                 fields["input_tokens"], fields["output_tokens"],
                 fields["cache_read_tokens"], fields["cache_creation_tokens"]),
            )
    except Exception as exc:
        logging.getLogger(__name__).warning("record_token_usage failed: %s", exc)


def get_token_usage_summary(days: int = 30) -> dict:
    """Return aggregated token usage totals, by-call-type breakdown, and daily series."""
    period = f"-{days} days"
    with _conn() as conn:
        type_rows = conn.execute(
            """SELECT call_type,
                      SUM(input_tokens)          AS input_tokens,
                      SUM(output_tokens)         AS output_tokens,
                      SUM(cache_read_tokens)     AS cache_read_tokens,
                      SUM(cache_creation_tokens) AS cache_creation_tokens
               FROM token_usage
               WHERE created_at >= datetime('now', ?)
               GROUP BY call_type""",
            (period,),
        ).fetchall()

        day_rows = conn.execute(
            """SELECT DATE(created_at)           AS date,
                      SUM(input_tokens)          AS input_tokens,
                      SUM(output_tokens)         AS output_tokens,
                      SUM(cache_read_tokens)     AS cache_read_tokens,
                      SUM(cache_creation_tokens) AS cache_creation_tokens
               FROM token_usage
               WHERE created_at >= datetime('now', ?)
               GROUP BY DATE(created_at)
               ORDER BY date""",
            (period,),
        ).fetchall()

    by_call_type = {
        r["call_type"]: {
            "input_tokens":          r["input_tokens"] or 0,
            "output_tokens":         r["output_tokens"] or 0,
            "cache_read_tokens":     r["cache_read_tokens"] or 0,
            "cache_creation_tokens": r["cache_creation_tokens"] or 0,
        }
        for r in type_rows
    }

    totals = {
        "input_tokens":          sum(v["input_tokens"]          for v in by_call_type.values()),
        "output_tokens":         sum(v["output_tokens"]         for v in by_call_type.values()),
        "cache_read_tokens":     sum(v["cache_read_tokens"]     for v in by_call_type.values()),
        "cache_creation_tokens": sum(v["cache_creation_tokens"] for v in by_call_type.values()),
    }

    by_day = [
        {
            "date":                  r["date"],
            "input_tokens":          r["input_tokens"] or 0,
            "output_tokens":         r["output_tokens"] or 0,
            "cache_read_tokens":     r["cache_read_tokens"] or 0,
            "cache_creation_tokens": r["cache_creation_tokens"] or 0,
        }
        for r in day_rows
    ]

    return {"period_days": days, "totals": totals, "by_call_type": by_call_type, "by_day": by_day}
