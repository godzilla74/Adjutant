"""Sub-agent execution via the Claude Agent SDK."""

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

_SUBAGENT_SYSTEM = (
    "You are a specialized sub-agent working under Hannah, "
    "the Executive Assistant to Justin Farmer, CEO of JTA Ventures, LLC. "
    "JTA Ventures operates four products: Ignitara (white-label GoHighLevel), "
    "Bullsi (coaching KPI SaaS), RetainerOps (retainer management SaaS), and "
    "Eligibility Console (medical/dental insurance verification for AI agents). "
    "Complete your assigned task thoroughly and return a clear, organized summary."
)


async def run_research_agent(task: str) -> str:
    """Spawn a web-research-focused sub-agent."""
    result = "Research agent completed with no output."

    async for message in query(
        prompt=task,
        options=ClaudeAgentOptions(
            allowed_tools=["WebSearch", "WebFetch"],
            max_turns=15,
            system_prompt=(
                _SUBAGENT_SYSTEM
                + " Focus on accurate, well-sourced research. Cite sources."
            ),
        ),
    ):
        if isinstance(message, ResultMessage):
            result = message.result

    return result


async def run_general_agent(task: str) -> str:
    """Spawn a general-purpose sub-agent with broader tool access."""
    result = "Agent completed with no output."

    async for message in query(
        prompt=task,
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Glob", "Grep", "WebSearch", "WebFetch"],
            max_turns=20,
            system_prompt=_SUBAGENT_SYSTEM,
        ),
    ):
        if isinstance(message, ResultMessage):
            result = message.result

    return result


_GMAIL_MCP = {
    "gmail": {
        "url": "http://localhost:8765/sse",
    }
}


async def run_email_agent(task: str) -> str:
    """Spawn a sub-agent with Gmail MCP access."""
    result = "Email agent completed with no output."

    async for message in query(
        prompt=task,
        options=ClaudeAgentOptions(
            mcp_servers=_GMAIL_MCP,
            max_turns=20,
            system_prompt=(
                _SUBAGENT_SYSTEM
                + " You have access to Gmail tools. Use them to read, search, "
                "draft, and send emails on Justin's behalf as instructed."
            ),
        ),
    ):
        if isinstance(message, ResultMessage):
            result = message.result

    return result
