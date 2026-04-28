"""Sub-agent execution via the Claude Code CLI."""

import asyncio
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

AGENT_TIMEOUT = 900  # seconds

_SUBAGENT_MODEL_FALLBACK = "claude-sonnet-4-6"
_OPENAI_PREFIXES = ("gpt-", "o1", "o3", "o4")


def _get_subagent_model() -> str:
    """Return the Claude model to use for sub-agents.

    Reads from env var first, then DB.  Always returns a Claude model —
    sub-agents run via the claude CLI and cannot use OpenAI models.
    """
    env_override = os.environ.get("AGENT_SUBAGENT_MODEL", "")
    if env_override and not env_override.startswith(_OPENAI_PREFIXES):
        return env_override
    try:
        from backend.db import get_agent_config
        model = get_agent_config().get("subagent_model", "")
        if model and not model.startswith(_OPENAI_PREFIXES):
            return model
    except Exception:
        pass
    return _SUBAGENT_MODEL_FALLBACK


_RESEARCH_SYSTEM = (
    "You are a specialized sub-agent. Complete your assigned task thoroughly "
    "and return a clear, organized summary. "
    "Focus on accurate, well-sourced research. Cite sources. Be concise."
)

_GENERAL_SYSTEM = (
    "You are a specialized sub-agent. Complete your assigned task thoroughly "
    "and return a clear, organized summary."
)

_RESEARCH_TOOLS = "WebSearch,WebFetch"
_GENERAL_TOOLS = "Read,Glob,Grep,WebSearch,WebFetch"


async def _run_claude_cli(
    task: str,
    allowed_tools: str,
    system_prompt: str,
    timeout: int = AGENT_TIMEOUT,
) -> str:
    cmd = [
        "claude", "-p", task,
        "--output-format", "json",
        "--allowedTools", allowed_tools,
        "--system-prompt", system_prompt,
        "--model", _get_subagent_model(),
        "--no-session-persistence",
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ},
            cwd=str(Path.home()),
        )
    except FileNotFoundError:
        return "Sub-agent failed: 'claude' executable not found on PATH."
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        try:
            await proc.communicate()
        except (asyncio.TimeoutError, OSError):
            pass
        return f"Sub-agent timed out after {timeout}s."

    raw = stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip()
        logger.error("Sub-agent failed (exit %d): %s", proc.returncode, err or raw)
        return f"Sub-agent failed (exit {proc.returncode}): {err or raw}"

    try:
        data = json.loads(raw)
        return data.get("result", raw)
    except json.JSONDecodeError:
        return raw


async def run_research_agent(task: str) -> str:
    """Spawn a web-research-focused sub-agent (15-minute hard cap)."""
    return await _run_claude_cli(task, _RESEARCH_TOOLS, _RESEARCH_SYSTEM)


async def run_general_agent(task: str) -> str:
    """Spawn a general-purpose sub-agent (15-minute hard cap)."""
    return await _run_claude_cli(task, _GENERAL_TOOLS, _GENERAL_SYSTEM)
