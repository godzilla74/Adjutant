import asyncio
import json
import pytest
from pathlib import Path
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
    with patch("agents.runner._subagent_uses_openai", return_value=False), \
         patch("agents.runner.asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result = await run_research_agent("Capital of France?")
    assert result == "Paris is the capital."


@pytest.mark.asyncio
async def test_general_agent_returns_result_field():
    from agents.runner import run_general_agent
    proc = _make_proc(_success_json("Done."))
    with patch("agents.runner._subagent_uses_openai", return_value=False), \
         patch("agents.runner.asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result = await run_general_agent("Summarize this.")
    assert result == "Done."


@pytest.mark.asyncio
async def test_research_agent_uses_correct_tools():
    from agents.runner import run_research_agent
    proc = _make_proc(_success_json("ok"))
    with patch("agents.runner._subagent_uses_openai", return_value=False), \
         patch("agents.runner.asyncio.create_subprocess_exec", AsyncMock(return_value=proc)) as mock_exec:
        await run_research_agent("some task")
    args = list(mock_exec.call_args[0])
    tools_idx = args.index("--allowedTools")
    assert args[tools_idx + 1] == "WebSearch,WebFetch"


@pytest.mark.asyncio
async def test_general_agent_uses_correct_tools():
    from agents.runner import run_general_agent
    proc = _make_proc(_success_json("ok"))
    with patch("agents.runner._subagent_uses_openai", return_value=False), \
         patch("agents.runner.asyncio.create_subprocess_exec", AsyncMock(return_value=proc)) as mock_exec:
        await run_general_agent("some task")
    args = list(mock_exec.call_args[0])
    tools_idx = args.index("--allowedTools")
    assert args[tools_idx + 1] == "Read,Glob,Grep,WebSearch,WebFetch"


@pytest.mark.asyncio
async def test_nonzero_exit_returns_error_message():
    from agents.runner import run_research_agent
    proc = _make_proc("", returncode=1, stderr="API key missing")
    with patch("agents.runner._subagent_uses_openai", return_value=False), \
         patch("agents.runner.asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result = await run_research_agent("task")
    assert "Sub-agent failed" in result
    assert "API key missing" in result
    assert "exit 1" in result


@pytest.mark.asyncio
async def test_json_parse_failure_returns_raw_output():
    from agents.runner import run_research_agent
    proc = _make_proc("plain text output, not json")
    with patch("agents.runner._subagent_uses_openai", return_value=False), \
         patch("agents.runner.asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result = await run_research_agent("task")
    assert result == "plain text output, not json"


@pytest.mark.asyncio
async def test_timeout_kills_process_and_returns_message():
    from agents.runner import run_research_agent
    proc = MagicMock()
    proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
    proc.kill = MagicMock()
    with patch("agents.runner._subagent_uses_openai", return_value=False), \
         patch("agents.runner.asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result = await run_research_agent("task")
    proc.kill.assert_called_once()
    assert "timed out" in result
    assert proc.communicate.call_count >= 2


@pytest.mark.asyncio
async def test_claude_not_on_path_returns_friendly_error():
    from agents.runner import run_research_agent
    with patch("agents.runner._subagent_uses_openai", return_value=False), \
         patch("agents.runner.asyncio.create_subprocess_exec", AsyncMock(side_effect=FileNotFoundError())):
        result = await run_research_agent("task")
    assert "claude" in result.lower()
    assert "PATH" in result and "not found" in result.lower()


def test_runner_importable():
    from agents.runner import run_research_agent, run_general_agent, run_extension_agent
    assert callable(run_research_agent)
    assert callable(run_general_agent)
    assert callable(run_extension_agent)


@pytest.mark.asyncio
async def test_extension_agent_uses_bypass_permissions_when_claude_available():
    from agents.runner import run_extension_agent
    proc = _make_proc(_success_json("done"))
    with patch("agents.runner._subagent_uses_openai", return_value=False), \
         patch("agents.runner.shutil.which", return_value="/usr/bin/claude"), \
         patch("agents.runner.asyncio.create_subprocess_exec", AsyncMock(return_value=proc)) as mock_exec:
        await run_extension_agent("do a task", "be helpful")
    args = list(mock_exec.call_args[0])
    assert "--permission-mode" in args
    assert "bypassPermissions" in args
    assert "--allowedTools" not in args


@pytest.mark.asyncio
async def test_extension_agent_uses_codex_when_claude_missing(tmp_path):
    from agents.runner import run_extension_agent
    output_file = tmp_path / "result.txt"

    async def _fake_exec(*args, **kwargs):
        # Write result to the -o output file path from the command args
        cmd = list(args)
        o_idx = cmd.index("-o")
        Path(cmd[o_idx + 1]).write_text("codex result")
        return _make_proc("", returncode=0)

    with patch("agents.runner.shutil.which", return_value=None), \
         patch("agents.runner._find_codex", return_value="/usr/bin/codex"), \
         patch("agents.runner.asyncio.create_subprocess_exec", side_effect=_fake_exec), \
         patch("backend.db.get_agent_config", return_value={"subagent_model": "gpt-4o", "openai_access_token": "tok"}):
        result = await run_extension_agent("do a task", "be helpful")
    assert result == "codex result"


@pytest.mark.asyncio
async def test_codex_cli_prepends_system_prompt_to_task():
    from agents.runner import run_extension_agent
    captured_cmd = []

    async def _fake_exec(*args, **kwargs):
        captured_cmd.extend(args)
        Path(args[list(args).index("-o") + 1]).write_text("ok")
        return _make_proc("", returncode=0)

    with patch("agents.runner.shutil.which", return_value=None), \
         patch("agents.runner._find_codex", return_value="/usr/bin/codex"), \
         patch("agents.runner.asyncio.create_subprocess_exec", side_effect=_fake_exec), \
         patch("backend.db.get_agent_config", return_value={"subagent_model": "gpt-4o", "openai_access_token": ""}):
        await run_extension_agent("the task", "the instructions")

    # The final positional arg should contain both system prompt and task
    prompt_arg = captured_cmd[-1]
    assert "the instructions" in prompt_arg
    assert "the task" in prompt_arg


@pytest.mark.asyncio
async def test_extension_agent_falls_back_to_provider_when_claude_missing():
    from agents.runner import run_extension_agent
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="provider result")]
    mock_provider = MagicMock()
    mock_provider.create = AsyncMock(return_value=mock_response)
    with patch("agents.runner.shutil.which", return_value=None), \
         patch("agents.runner._find_codex", return_value=None), \
         patch("backend.provider.make_provider", return_value=mock_provider), \
         patch("backend.db.get_agent_config", return_value={"subagent_model": "gpt-4o"}):
        result = await run_extension_agent("do a task", "be helpful")
    assert result == "provider result"
    mock_provider.create.assert_called_once()
