"""Sub-agent execution via the Claude Agent SDK."""

import asyncio
import logging
import os

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
from claude_agent_sdk._errors import ProcessError

logger = logging.getLogger(__name__)

AGENT_TIMEOUT = 300  # seconds — raised from 180 to give complex tasks more room

# Model used for sub-agents. Defaults to sonnet to control cost.
# Override with HANNAH_SUBAGENT_MODEL env var (e.g. "opus", "sonnet", "haiku",
# or a full model ID like "claude-sonnet-4-6").
SUBAGENT_MODEL: str = os.environ.get("HANNAH_SUBAGENT_MODEL", "sonnet")

_SUBAGENT_SYSTEM = (
    "You are a specialized sub-agent. Complete your assigned task thoroughly "
    "and return a clear, organized summary."
)


def _make_stderr_logger(label: str) -> list[str]:
    """Return a stderr buffer and a callback that logs lines into it."""
    buf: list[str] = []

    def _cb(line: str) -> None:
        buf.append(line)
        logger.debug("[%s stderr] %s", label, line.rstrip())

    return buf, _cb


async def _run_research_agent_inner(task: str) -> str:
    stderr_buf, stderr_cb = _make_stderr_logger("research-agent")
    result = "Research agent completed with no output."
    try:
        async for message in query(
            prompt=task,
            options=ClaudeAgentOptions(
                model=SUBAGENT_MODEL,
                allowed_tools=["WebSearch", "WebFetch"],
                max_turns=8,
                system_prompt=(
                    _SUBAGENT_SYSTEM
                    + " Focus on accurate, well-sourced research. Cite sources. Be concise."
                ),
                stderr=stderr_cb,
            ),
        ):
            if isinstance(message, ResultMessage):
                result = message.result
    except ProcessError as e:
        real_stderr = "\n".join(stderr_buf).strip()
        detail = real_stderr or str(e)
        logger.error("Research sub-agent process error: %s", detail)
        return f"Sub-agent process failed: {detail}"
    return result


async def run_research_agent(task: str) -> str:
    """Spawn a web-research-focused sub-agent (5-minute hard cap)."""
    try:
        return await asyncio.wait_for(_run_research_agent_inner(task), timeout=AGENT_TIMEOUT)
    except asyncio.TimeoutError:
        return f"Research agent timed out after {AGENT_TIMEOUT}s. Partial results may be incomplete."


async def _run_general_agent_inner(task: str) -> str:
    stderr_buf, stderr_cb = _make_stderr_logger("general-agent")
    result = "Agent completed with no output."
    try:
        async for message in query(
            prompt=task,
            options=ClaudeAgentOptions(
                model=SUBAGENT_MODEL,
                allowed_tools=["Read", "Glob", "Grep", "WebSearch", "WebFetch"],
                max_turns=10,
                system_prompt=_SUBAGENT_SYSTEM,
                stderr=stderr_cb,
            ),
        ):
            if isinstance(message, ResultMessage):
                result = message.result
    except ProcessError as e:
        real_stderr = "\n".join(stderr_buf).strip()
        detail = real_stderr or str(e)
        logger.error("General sub-agent process error: %s", detail)
        return f"Sub-agent process failed: {detail}"
    return result


async def run_general_agent(task: str) -> str:
    """Spawn a general-purpose sub-agent (5-minute hard cap)."""
    try:
        return await asyncio.wait_for(_run_general_agent_inner(task), timeout=AGENT_TIMEOUT)
    except asyncio.TimeoutError:
        return f"General agent timed out after {AGENT_TIMEOUT}s."
