"""Filesystem watcher — re-walks content directory on changes.

Uses watchfiles with built-in debouncing. Only enabled in dev mode
via MEDIASTUDYSHELF_WATCH=1.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from watchfiles import awatch

from mediastudyshelf.routes import set_courses
from mediastudyshelf.walker import walk_content

logger = logging.getLogger(__name__)

DEBOUNCE_MS = 500


async def watch_content(content_path: Path) -> None:
    """Watch content_path for changes and re-walk on each batch."""
    logger.info("Content watcher started: %s", content_path)
    try:
        async for changes in awatch(content_path, debounce=DEBOUNCE_MS, step=100):
            # Pick one changed path for the log message
            sample_change = next(iter(changes))
            change_type, changed_path = sample_change
            t0 = time.monotonic()
            courses = walk_content(content_path)
            set_courses(courses, content_path)
            elapsed = (time.monotonic() - t0) * 1000
            logger.info(
                "Content re-walked in %.0fms — triggered by %s (%d change(s))",
                elapsed,
                changed_path,
                len(changes),
            )
    except asyncio.CancelledError:
        logger.info("Content watcher stopped")
