# backend/discord_state.py
"""Shared state for hot-reloading the Discord bot without circular imports."""
from typing import Callable, Awaitable

_restarter: Callable[[str], Awaitable[None]] | None = None


def register(fn: Callable[[str], Awaitable[None]]) -> None:
    global _restarter
    _restarter = fn


async def restart(token: str) -> None:
    if _restarter is not None:
        await _restarter(token)
