"""Media enrichment — PDF page counts and audio/video durations.

All results are cached in memory keyed by (path, mtime) so expensive
operations don't rerun for unchanged files.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger(__name__)

# In-memory cache: (resolved_path_str, mtime_ns) → value
_cache: dict[tuple[str, int], int | None] = {}


def clear_cache() -> None:
    """Drop all cached enrichment results (used on full re-walks)."""
    _cache.clear()


def _cache_key(path: Path) -> tuple[str, int]:
    return (str(path.resolve()), path.stat().st_mtime_ns)


def get_pdf_page_count(path: Path) -> int | None:
    """Return the number of pages in a PDF, or None on failure."""
    key = _cache_key(path)
    if key in _cache:
        return _cache[key]

    try:
        reader = PdfReader(path)
        count = len(reader.pages)
    except Exception:
        logger.warning("Failed to read PDF page count: %s", path)
        count = None

    _cache[key] = count
    return count


def get_media_duration(path: Path) -> int | None:
    """Return duration in seconds (rounded) via ffprobe, or None on failure."""
    key = _cache_key(path)
    if key in _cache:
        return _cache[key]

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("ffprobe failed (exit %d) for: %s", result.returncode, path)
            _cache[key] = None
            return None

        data = json.loads(result.stdout)
        raw = data.get("format", {}).get("duration")
        if raw is None:
            logger.warning("ffprobe returned no duration for: %s", path)
            _cache[key] = None
            return None

        duration = round(float(raw))
    except FileNotFoundError:
        logger.error("ffprobe not found on PATH — install ffmpeg to enable media duration extraction")
        duration = None
    except Exception:
        logger.warning("Failed to get duration for: %s", path, exc_info=True)
        duration = None

    _cache[key] = duration
    return duration
