"""Runtime state shared across the app.

Holds the walked course tree and the root it was walked from, repopulated at
startup and on each watcher-triggered reload. Kept paired so ``media_url``
always resolves against the same root the courses were walked from.
"""

from __future__ import annotations

from pathlib import Path

from mediastudyshelf.core.types.content import CourseNode

_courses: list[CourseNode] = []
_content_root: Path = Path(".")


def set_courses(courses: list[CourseNode], content_root: Path) -> None:
    """Store the walked course tree and the root it was walked from."""
    global _courses, _content_root
    _courses = courses
    _content_root = content_root


def get_courses() -> list[CourseNode]:
    return _courses


def get_content_root() -> Path:
    return _content_root


def media_url(file_path: Path) -> str:
    """Convert an absolute file path to a /media/assets/... URL."""
    rel = file_path.relative_to(_content_root)
    return "/media/assets/" + str(rel)
