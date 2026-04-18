# backend/telegram_state.py
"""Shared state for hot-reloading the Telegram bot without circular imports."""
from typing import Callable, Awaitable

_restarter: Callable[[str, str], Awaitable[None]] | None = None


def register(fn: Callable[[str, str], Awaitable[None]]) -> None:
    global _restarter
    _restarter = fn


async def restart(token: str, chat_id: str) -> None:
    if _restarter is not None:
        await _restarter(token, chat_id)
