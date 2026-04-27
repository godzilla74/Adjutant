import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_proc(stdout: str, returncode: int = 0, stderr: str = ""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout.encode(), stderr.encode()))
    proc.kill = MagicMock()
    return proc


def _success_json(text: str) -> str:
    return json.dumps({"type": "result", "subtype": "success", "result": text, "is_error": False})


@pytest.mark.asyncio
async def test_research_agent_returns_result_field():
    from agents.runner import run_research_agent
    proc = _make_proc(_success_json("Paris is the capital."))
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result = await run_research_agent("Capital of France?")
    assert result == "Paris is the capital."


@pytest.mark.asyncio
async def test_general_agent_returns_result_field():
    from agents.runner import run_general_agent
    proc = _make_proc(_success_json("Done."))
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result = await run_general_agent("Summarize this.")
    assert result == "Done."


@pytest.mark.asyncio
async def test_research_agent_uses_correct_tools():
    from agents.runner import run_research_agent
    proc = _make_proc(_success_json("ok"))
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)) as mock_exec:
        await run_research_agent("some task")
    args = list(mock_exec.call_args[0])
    tools_idx = args.index("--allowedTools")
    assert args[tools_idx + 1] == "WebSearch,WebFetch"


@pytest.mark.asyncio
async def test_general_agent_uses_correct_tools():
    from agents.runner import run_general_agent
    proc = _make_proc(_success_json("ok"))
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)) as mock_exec:
        await run_general_agent("some task")
    args = list(mock_exec.call_args[0])
    tools_idx = args.index("--allowedTools")
    assert args[tools_idx + 1] == "Read,Glob,Grep,WebSearch,WebFetch"


@pytest.mark.asyncio
async def test_nonzero_exit_returns_error_message():
    from agents.runner import run_research_agent
    proc = _make_proc("", returncode=1, stderr="API key missing")
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result = await run_research_agent("task")
    assert "Sub-agent failed" in result
    assert "API key missing" in result


@pytest.mark.asyncio
async def test_json_parse_failure_returns_raw_output():
    from agents.runner import run_research_agent
    proc = _make_proc("plain text output, not json")
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result = await run_research_agent("task")
    assert result == "plain text output, not json"


@pytest.mark.asyncio
async def test_timeout_kills_process_and_returns_message():
    from agents.runner import run_research_agent
    proc = MagicMock()
    proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
    proc.kill = MagicMock()
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result = await run_research_agent("task")
    proc.kill.assert_called_once()
    assert "timed out" in result


@pytest.mark.asyncio
async def test_claude_not_on_path_returns_friendly_error():
    from agents.runner import run_research_agent
    with patch("asyncio.create_subprocess_exec", AsyncMock(side_effect=FileNotFoundError())):
        result = await run_research_agent("task")
    assert "claude" in result.lower()
    assert "PATH" in result or "not found" in result.lower()


def test_runner_importable():
    from agents.runner import run_research_agent, run_general_agent
    assert callable(run_research_agent)
    assert callable(run_general_agent)
