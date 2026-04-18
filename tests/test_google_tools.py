# tests/test_google_tools.py
import asyncio
import json
from unittest.mock import AsyncMock, patch


def test_email_task_removed_from_tool_definitions():
    """email_task must no longer exist — it's replaced by gmail_* tools."""
    from core.tools import TOOLS_DEFINITIONS
    names = [t["name"] for t in TOOLS_DEFINITIONS]
    assert "email_task" not in names


def test_gmail_tools_in_definitions():
    from core.tools import _GMAIL_TOOLS
    names = [t["name"] for t in _GMAIL_TOOLS]
    assert "gmail_search" in names
    assert "gmail_read" in names
    assert "gmail_send" in names
    assert "gmail_draft" in names


def test_gmail_search_tool_schema():
    from core.tools import _GMAIL_TOOLS
    tool = next(t for t in _GMAIL_TOOLS if t["name"] == "gmail_search")
    props = tool["input_schema"]["properties"]
    required = tool["input_schema"]["required"]
    assert "product_id" in props
    assert "query" in props
    assert "product_id" in required
    assert "query" in required


def test_gmail_send_tool_schema():
    from core.tools import _GMAIL_TOOLS
    tool = next(t for t in _GMAIL_TOOLS if t["name"] == "gmail_send")
    props = tool["input_schema"]["properties"]
    required = tool["input_schema"]["required"]
    assert "product_id" in required
    assert "to" in required
    assert "subject" in required
    assert "body" in required
    assert "thread_id" in props  # optional


def test_execute_gmail_search():
    async def run():
        with patch("backend.google_api.gmail_search", new=AsyncMock(return_value='{"count": 2}')):
            from core.tools import execute_tool
            result = await execute_tool("gmail_search", {"product_id": "p1", "query": "test"})
        assert "2" in result
    asyncio.run(run())


def test_calendar_tools_in_definitions():
    from core.tools import _CALENDAR_TOOLS
    names = [t["name"] for t in _CALENDAR_TOOLS]
    assert "calendar_list_events" in names
    assert "calendar_create_event" in names
    assert "calendar_find_free_time" in names


def test_calendar_create_event_schema():
    from core.tools import _CALENDAR_TOOLS
    tool = next(t for t in _CALENDAR_TOOLS if t["name"] == "calendar_create_event")
    props = tool["input_schema"]["properties"]
    required = tool["input_schema"]["required"]
    assert "product_id" in required
    assert "title" in required
    assert "start" in required
    assert "end" in required
    assert "attendees" in props  # optional
    assert "description" in props  # optional


def test_execute_calendar_list_events():
    async def run():
        with patch("backend.google_api.calendar_list_events", new=AsyncMock(return_value='{"events": [], "count": 0}')):
            from core.tools import execute_tool
            result = await execute_tool(
                "calendar_list_events",
                {"product_id": "p1", "start": "2026-04-18T00:00:00Z", "end": "2026-04-18T23:59:59Z"},
            )
        assert "events" in result
    asyncio.run(run())


import importlib
import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    with db_mod._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO products (id, name, icon_label, color) "
            "VALUES ('prod-1', 'Prod 1', 'P1', '#000')"
        )
    return db_mod


def test_gmail_send_approve_tier_creates_review_item(db):
    db.set_action_autonomy("prod-1", "email", "approve", None)
    async def run():
        with patch("backend.google_api.gmail_send", new=AsyncMock()) as mock_send:
            import importlib as il
            import core.tools as tools_mod
            il.reload(tools_mod)
            result = json.loads(await tools_mod.execute_tool(
                "gmail_send",
                {"product_id": "prod-1", "to": "x@x.com", "subject": "Hi", "body": "Body"},
            ))
            mock_send.assert_not_called()
        assert result.get("queued_for_review") is True
    asyncio.run(run())


def test_gmail_send_auto_tier_sends_immediately(db):
    db.set_action_autonomy("prod-1", "email", "auto", None)
    async def run():
        with patch("backend.google_api.gmail_send", new=AsyncMock(return_value='{"sent": true}')):
            import importlib as il
            import core.tools as tools_mod
            il.reload(tools_mod)
            result = await tools_mod.execute_tool(
                "gmail_send",
                {"product_id": "prod-1", "to": "x@x.com", "subject": "Hi", "body": "Body"},
            )
        assert "sent" in result
    asyncio.run(run())


def test_calendar_create_event_approve_tier_creates_review_item(db):
    db.set_action_autonomy("prod-1", "agent_review", "approve", None)
    async def run():
        with patch("backend.google_api.calendar_create_event", new=AsyncMock()) as mock_create:
            from core.tools import execute_tool
            result = json.loads(await execute_tool(
                "calendar_create_event",
                {
                    "product_id": "prod-1", "title": "Sync",
                    "start": "2026-04-18T10:00:00Z", "end": "2026-04-18T10:30:00Z",
                },
            ))
            mock_create.assert_not_called()
        assert result.get("queued_for_review") is True
    asyncio.run(run())


def test_get_tools_for_product_no_connections(db):
    """Gmail/Calendar tools must be absent when no OAuth connection exists."""
    from core.tools import get_tools_for_product
    tools = get_tools_for_product("prod-1")
    names = [t["name"] for t in tools]
    assert "gmail_search" not in names
    assert "gmail_send" not in names
    assert "calendar_list_events" not in names


def test_get_tools_for_product_with_gmail(db):
    """Gmail tools appear when product has a Gmail connection."""
    db.save_oauth_connection("prod-1", "gmail", "a@x.com", "tok", "ref", "2099-01-01T00:00:00+00:00", "s")
    from core.tools import get_tools_for_product
    tools = get_tools_for_product("prod-1")
    names = [t["name"] for t in tools]
    assert "gmail_search" in names
    assert "gmail_read" in names
    assert "gmail_send" in names
    assert "gmail_draft" in names
    assert "calendar_list_events" not in names


def test_get_tools_for_product_with_calendar(db):
    """Calendar tools appear when product has a Calendar connection."""
    db.save_oauth_connection("prod-1", "google_calendar", "a@x.com", "tok", "ref", "2099-01-01T00:00:00+00:00", "s")
    from core.tools import get_tools_for_product
    tools = get_tools_for_product("prod-1")
    names = [t["name"] for t in tools]
    assert "calendar_list_events" in names
    assert "calendar_create_event" in names
    assert "calendar_find_free_time" in names
    assert "gmail_search" not in names


def test_social_tools_in_lists():
    from core.tools import _TWITTER_TOOLS, _LINKEDIN_TOOLS, _FACEBOOK_TOOLS, _INSTAGRAM_TOOLS
    assert any(t["name"] == "twitter_post" for t in _TWITTER_TOOLS)
    assert any(t["name"] == "linkedin_post" for t in _LINKEDIN_TOOLS)
    assert any(t["name"] == "facebook_post" for t in _FACEBOOK_TOOLS)
    assert any(t["name"] == "instagram_post" for t in _INSTAGRAM_TOOLS)


def test_social_tools_not_in_tools_definitions():
    from core.tools import TOOLS_DEFINITIONS
    names = [t["name"] for t in TOOLS_DEFINITIONS]
    assert "twitter_post" not in names
    assert "instagram_post" not in names


def test_instagram_post_schema_requires_image_url():
    from core.tools import _INSTAGRAM_TOOLS
    tool = next(t for t in _INSTAGRAM_TOOLS if t["name"] == "instagram_post")
    assert "image_url" in tool["input_schema"]["required"]
    assert "caption" in tool["input_schema"]["required"]


def test_get_tools_for_product_with_twitter(db):
    db.save_oauth_connection("prod-1", "twitter", "@handle", "tok", "ref", "2099-01-01T00:00:00+00:00", "s")
    import importlib as il
    import core.tools as tools_mod
    il.reload(tools_mod)
    tools = tools_mod.get_tools_for_product("prod-1")
    names = [t["name"] for t in tools]
    assert "twitter_post" in names
    assert "linkedin_post" not in names
    assert "gmail_search" not in names


def test_get_tools_for_product_with_meta(db):
    db.save_oauth_connection("prod-1", "facebook", "page-123", "tok", "", "2099-01-01T00:00:00+00:00", "s")
    db.save_oauth_connection("prod-1", "instagram", "ig-456", "tok", "", "2099-01-01T00:00:00+00:00", "s")
    import importlib as il
    import core.tools as tools_mod
    il.reload(tools_mod)
    tools = tools_mod.get_tools_for_product("prod-1")
    names = [t["name"] for t in tools]
    assert "facebook_post" in names
    assert "instagram_post" in names
    assert "linkedin_post" not in names


def test_twitter_post_approve_tier_creates_review_item(db):
    db.set_action_autonomy("prod-1", "social_post", "approve", None)
    async def run():
        with patch("backend.social_api.twitter_post", new=AsyncMock()) as mock_post:
            import importlib as il
            import core.tools as tools_mod
            il.reload(tools_mod)
            result = json.loads(await tools_mod.execute_tool(
                "twitter_post",
                {"product_id": "prod-1", "text": "Hello world"},
            ))
            mock_post.assert_not_called()
        assert result.get("queued_for_review") is True
    asyncio.run(run())


def test_twitter_post_auto_tier_posts_immediately(db):
    db.set_action_autonomy("prod-1", "social_post", "auto", None)
    async def run():
        with patch("backend.social_api.twitter_post", new=AsyncMock(return_value='{"posted": true}')):
            import importlib as il
            import core.tools as tools_mod
            il.reload(tools_mod)
            result = await tools_mod.execute_tool(
                "twitter_post",
                {"product_id": "prod-1", "text": "Hello world"},
            )
        assert "posted" in result
    asyncio.run(run())
