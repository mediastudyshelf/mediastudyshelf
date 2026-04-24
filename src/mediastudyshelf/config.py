"""Application configuration — reads from environment variables."""

import os
from pathlib import Path


def get_content_path() -> Path:
    """Return the resolved content directory path.

    Reads from MEDIASTUDYSHELF_CONTENT_PATH, defaulting to ./sample-content.
    """
    raw = os.environ.get("MEDIASTUDYSHELF_CONTENT_PATH", "./sample-content")
    return Path(raw).resolve()


def watch_enabled() -> bool:
    """Return True if filesystem watching is enabled.

    Enabled by setting MEDIASTUDYSHELF_WATCH=1.
    """
    return os.environ.get("MEDIASTUDYSHELF_WATCH", "").strip() == "1"


def serve_frontend() -> bool:
    """Return True if the built frontend should be served.

    Enabled by setting SERVE_FRONTEND=1.
    """
    return os.environ.get("SERVE_FRONTEND", "").strip() == "1"


def get_frontend_dist() -> Path:
    """Return the path to the built frontend dist directory."""
    return Path(__file__).resolve().parent.parent.parent / "client" / "dist"
