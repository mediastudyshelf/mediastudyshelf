"""Streaming package — HLS session orchestration.

Public surface:

- ``SessionManager`` — per-viewer HLS session lifecycle (lives in
  ``session_manager.py``; re-exported here for convenience).
- ``get_manager`` / ``set_manager`` — module-level singleton accessors;
  ``main.py`` calls ``set_manager`` once at startup.
- ``session_gc_loop`` — background task that periodically GCs idle sessions.

The singleton lives in this ``__init__`` (rather than a submodule) so that
``from mediastudyshelf.streaming import get_manager`` is the canonical access
path and the package's public API is visible at a glance.
"""

import asyncio

from mediastudyshelf.streaming.constants import SESSION_GC_INTERVAL
from mediastudyshelf.streaming.session_manager import SessionManager

_manager: SessionManager | None = None


def get_manager() -> SessionManager:
    assert _manager is not None, "SessionManager not initialized"
    return _manager


def set_manager(manager: SessionManager) -> None:
    global _manager
    _manager = manager


async def session_gc_loop() -> None:
    """Background task that periodically cleans up idle sessions."""
    while True:
        await asyncio.sleep(SESSION_GC_INTERVAL)
        if _manager:
            _manager.gc_expired()


__all__ = ["SessionManager", "get_manager", "set_manager", "session_gc_loop"]
