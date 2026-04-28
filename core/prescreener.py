"""Haiku pre-screener: classify user messages and select tool groups before Sonnet."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from backend.provider import AnthropicProvider, OpenAIProvider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a routing agent for an AI executive assistant. Given a user message, decide how to handle it.

Return JSON only — no prose, no markdown. One of two shapes:

If you can answer directly without any tools or data access:
{"route": "haiku", "response": "your full answer here"}

If the main agent is needed:
{"route": "sonnet", "tool_groups": ["core", "email"]}

Route to haiku ONLY for: greetings, simple factual questions answerable without data access, \
conversational acknowledgments, or short replies requiring no tools.

Route to sonnet for: anything requiring tool use, task execution, accessing email/calendar/notes, \
managing objectives or workstreams, complex reasoning, or anything you are uncertain about.

Always include "core" in tool_groups. Only include groups from the available list provided.\
"""


@dataclass
class PrescreerResult:
    """Routing decision from the prescreener: respond directly or delegate to Sonnet."""
    route: Literal["haiku", "sonnet"]
    tool_groups: list[str] = field(default_factory=list)
    response: str | None = None
    usage: object | None = None


def _fallback(available_groups: list[str]) -> PrescreerResult:
    return PrescreerResult(route="sonnet", tool_groups=list({"core"} | set(available_groups)))


async def prescreen(
    message: str,
    available_groups: list[str],
    provider: "AnthropicProvider | OpenAIProvider",
    model: str,
) -> PrescreerResult:
    """Classify a user message and return routing + tool group selection.

    Falls back to route=sonnet with all available_groups on any error.
    """
    system = _SYSTEM_PROMPT + f"\n\nAvailable tool groups: {available_groups}"
    try:
        resp = await provider.create(
            model=model,
            system=system,
            messages=[{"role": "user", "content": message}],
            max_tokens=512,
        )
        data = json.loads(resp.content[0].text.strip())
        route = data.get("route")

        if route == "haiku":
            response = data.get("response", "")
            if not isinstance(response, str):
                return _fallback(available_groups)
            return PrescreerResult(route="haiku", response=response, usage=resp.usage)

        if route == "sonnet":
            groups = data.get("tool_groups", [])
            if not isinstance(groups, list):
                return _fallback(available_groups)
            valid = set(available_groups)
            merged = list({"core"} | (set(groups) & valid))
            return PrescreerResult(route="sonnet", tool_groups=merged, usage=resp.usage)

        return _fallback(available_groups)

    except Exception:
        logger.debug("Prescreener fallback triggered", exc_info=True)
        return _fallback(available_groups)
