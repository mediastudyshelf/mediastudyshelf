"""Content domain types — the in-memory tree the walker produces.

These dataclasses live here (not next to the walker) so consumers can use
``CourseNode`` etc. without pulling in filesystem-walking code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FileEntry:
    filename: str
    category: str  # video | pdf | audio | extra
    path: Path  # absolute path on disk
    size_bytes: int = 0
    is_primary: bool = False  # only meaningful for PDFs
    label: str = ""  # display label
    pages: int | None = None  # PDF page count
    duration_seconds: int | None = None  # video/audio duration


@dataclass
class ClassNode:
    slug: str
    title: str
    order: int | None
    path: Path
    videos: list[FileEntry] = field(default_factory=list)
    pdfs: list[FileEntry] = field(default_factory=list)
    audio: list[FileEntry] = field(default_factory=list)
    extras: list[FileEntry] = field(default_factory=list)


@dataclass
class ModuleNode:
    slug: str
    title: str
    order: int | None
    path: Path
    classes: list[ClassNode] = field(default_factory=list)


@dataclass
class CourseNode:
    slug: str
    title: str
    order: int | None
    path: Path
    modules: list[ModuleNode] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
