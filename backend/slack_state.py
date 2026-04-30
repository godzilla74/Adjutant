# backend/slack_state.py
"""Shared state for hot-reloading the Slack bot without circular imports."""
from typing import Callable, Awaitable

_restarter: Callable[[str, str], Awaitable[None]] | None = None


def register(fn: Callable[[str, str], Awaitable[None]]) -> None:
    global _restarter
    _restarter = fn


async def restart(bot_token: str, app_token: str) -> None:
    if _restarter is not None:
        await _restarter(bot_token, app_token)
