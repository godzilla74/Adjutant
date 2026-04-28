"""Tests for token usage DB helpers."""
import importlib
import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    return db_mod


def test_record_token_usage_inserts_row(db):
    class FakeUsage:
        input_tokens = 100
        output_tokens = 50
        cache_read_input_tokens = 20
        cache_creation_input_tokens = 5

    db.record_token_usage("prod-1", "agent", "anthropic", "claude-sonnet-4-6", FakeUsage())
    summary = db.get_token_usage_summary(days=30)
    assert summary["totals"]["input_tokens"] == 100
    assert summary["totals"]["output_tokens"] == 50
    assert summary["totals"]["cache_read_tokens"] == 20
    assert summary["totals"]["cache_creation_tokens"] == 5


def test_normalize_usage_anthropic(db):
    class FakeUsage:
        input_tokens = 200
        output_tokens = 80
        cache_read_input_tokens = 150
        cache_creation_input_tokens = 10

    result = db._normalize_usage("anthropic", FakeUsage())
    assert result == {
        "input_tokens": 200,
        "output_tokens": 80,
        "cache_read_tokens": 150,
        "cache_creation_tokens": 10,
    }


def test_normalize_usage_openai(db):
    class Details:
        cached_tokens = 60

    class FakeUsage:
        prompt_tokens = 300
        completion_tokens = 90
        prompt_tokens_details = Details()

    result = db._normalize_usage("openai", FakeUsage())
    assert result == {
        "input_tokens": 300,
        "output_tokens": 90,
        "cache_read_tokens": 60,
        "cache_creation_tokens": 0,
    }


def test_normalize_usage_openai_no_details(db):
    class FakeUsage:
        prompt_tokens = 300
        completion_tokens = 90
        prompt_tokens_details = None

    result = db._normalize_usage("openai", FakeUsage())
    assert result["cache_read_tokens"] == 0


def test_get_token_usage_summary_by_call_type(db):
    class U:
        def __init__(self, i, o):
            self.input_tokens = i
            self.output_tokens = o
            self.cache_read_input_tokens = 0
            self.cache_creation_input_tokens = 0

    db.record_token_usage("p1", "agent",       "anthropic", "claude-sonnet-4-6", U(500, 200))
    db.record_token_usage("p1", "prescreener", "anthropic", "claude-haiku-4-5-20251001", U(100, 10))
    db.record_token_usage("p1", "compaction",  "anthropic", "claude-haiku-4-5-20251001", U(300, 50))

    summary = db.get_token_usage_summary(days=30)
    assert summary["by_call_type"]["agent"]["input_tokens"] == 500
    assert summary["by_call_type"]["prescreener"]["input_tokens"] == 100
    assert summary["by_call_type"]["compaction"]["input_tokens"] == 300
    assert summary["totals"]["input_tokens"] == 900


def test_record_token_usage_survives_exception(db):
    # Passing None as usage — should not raise
    db.record_token_usage("p1", "agent", "anthropic", "claude-sonnet-4-6", None)


def test_get_token_usage_summary_empty(db):
    summary = db.get_token_usage_summary(days=30)
    assert summary["totals"]["input_tokens"] == 0
    assert summary["by_call_type"] == {}
    assert summary["by_day"] == []


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("AGENT_PASSWORD", "testpw")
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()

    import backend.api as api_mod
    importlib.reload(api_mod)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(api_mod.router)
    return TestClient(app)


def test_token_usage_endpoint_returns_summary(api_client):
    resp = api_client.get(
        "/api/token-usage?days=30",
        headers={"X-Agent-Password": "testpw"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "totals" in body
    assert "by_call_type" in body
    assert "by_day" in body
    assert body["period_days"] == 30
    assert body["totals"]["input_tokens"] == 0


def test_token_usage_endpoint_requires_auth(api_client):
    resp = api_client.get("/api/token-usage")
    assert resp.status_code == 401


def test_agent_config_per_product(api_client):
    """GET /api/agent-config?product_id= returns per-product resolved config."""
    # Create a product first
    resp = api_client.post(
        "/api/products",
        json={"id": "test-p1", "name": "Test", "icon_label": "T", "color": "#fff"},
        headers={"X-Agent-Password": "testpw"},
    )
    # GET per-product config — should return global defaults
    resp = api_client.get(
        "/api/agent-config?product_id=test-p1",
        headers={"X-Agent-Password": "testpw"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "agent_model" in body
    assert "subagent_model" in body
    assert "prescreener_model" in body

    # PUT per-product override
    resp = api_client.put(
        "/api/agent-config",
        json={"product_id": "test-p1", "agent_model": "gpt-4o"},
        headers={"X-Agent-Password": "testpw"},
    )
    assert resp.status_code == 200
    assert resp.json()["agent_model"] == "gpt-4o"

    # GET again — should reflect the override
    resp = api_client.get(
        "/api/agent-config?product_id=test-p1",
        headers={"X-Agent-Password": "testpw"},
    )
    assert resp.json()["agent_model"] == "gpt-4o"
