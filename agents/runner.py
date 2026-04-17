"""Sub-agent execution via the Claude Agent SDK."""

import asyncio
import os

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

AGENT_TIMEOUT = 180  # seconds — hard cap per agent run

# Model used for sub-agents. Defaults to sonnet to control cost.
# Override with HANNAH_SUBAGENT_MODEL env var (e.g. "opus", "sonnet", "haiku",
# or a full model ID like "claude-sonnet-4-6").
SUBAGENT_MODEL: str = os.environ.get("HANNAH_SUBAGENT_MODEL", "sonnet")

_SUBAGENT_SYSTEM = (
    "You are a specialized sub-agent. Complete your assigned task thoroughly "
    "and return a clear, organized summary."
)


async def _run_research_agent_inner(task: str) -> str:
    result = "Research agent completed with no output."
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
        ),
    ):
        if isinstance(message, ResultMessage):
            result = message.result
    return result


async def run_research_agent(task: str) -> str:
    """Spawn a web-research-focused sub-agent (3-minute hard cap)."""
    try:
        return await asyncio.wait_for(_run_research_agent_inner(task), timeout=AGENT_TIMEOUT)
    except asyncio.TimeoutError:
        return f"Research agent timed out after {AGENT_TIMEOUT}s. Partial results may be incomplete."


async def _run_general_agent_inner(task: str) -> str:
    result = "Agent completed with no output."
    async for message in query(
        prompt=task,
        options=ClaudeAgentOptions(
            model=SUBAGENT_MODEL,
            allowed_tools=["Read", "Glob", "Grep", "WebSearch", "WebFetch"],
            max_turns=10,
            system_prompt=_SUBAGENT_SYSTEM,
        ),
    ):
        if isinstance(message, ResultMessage):
            result = message.result
    return result


async def run_general_agent(task: str) -> str:
    """Spawn a general-purpose sub-agent (3-minute hard cap)."""
    try:
        return await asyncio.wait_for(_run_general_agent_inner(task), timeout=AGENT_TIMEOUT)
    except asyncio.TimeoutError:
        return f"General agent timed out after {AGENT_TIMEOUT}s."


