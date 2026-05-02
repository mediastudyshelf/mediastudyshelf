"""Filesystem content walker — builds a course tree from a folder structure."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── File classification by extension ────────────────────────────────────────

VIDEO_EXTS = {".mp4", ".webm", ".mov", ".ts", ".mkv", ".avi"}
PDF_EXTS = {".pdf"}
AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".ogg"}

PRIMARY_PDF_NAMES = {"lesson.pdf", "main.pdf"}

# ── Naming helpers ──────────────────────────────────────────────────────────

_PREFIX_RE = re.compile(r"^(\d{2,3})-(.+)$")


def parse_folder_name(name: str) -> tuple[int | None, str]:
    """Return (sort_order, display_title) from a folder name.

    Numeric prefix is stripped for display. Kebab-case is converted to
    sentence case: ``feedback-loops`` → ``Feedback loops``.
    """
    m = _PREFIX_RE.match(name)
    if m:
        order = int(m.group(1))
        raw = m.group(2)
    else:
        order = None
        raw = name
    title = raw.replace("-", " ").capitalize()
    return order, title


def slug_from_name(name: str) -> str:
    """Strip numeric prefix to get the URL slug."""
    m = _PREFIX_RE.match(name)
    return m.group(2) if m else name


def classify_file(filename: str) -> str:
    """Return one of 'video', 'pdf', 'audio', 'extra'."""
    ext = Path(filename).suffix.lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in PDF_EXTS:
        return "pdf"
    if ext in AUDIO_EXTS:
        return "audio"
    return "extra"


def file_display_name(filename: str) -> str:
    """Filename without extension, kebab → sentence case."""
    stem = Path(filename).stem
    return stem.replace("-", " ").replace("_", " ").capitalize()


# ── Data structures ─────────────────────────────────────────────────────────


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


# ── Optional metadata loading ──────────────────────────────────────────────


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file if it exists, else return empty dict."""
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


# ── Primary PDF resolution ─────────────────────────────────────────────────


def _resolve_primary_pdf(pdfs: list[FileEntry], metadata: dict[str, Any]) -> None:
    """Mark one PDF as primary, following the spec's resolution order.

    1. ``class.json`` override via ``primary_pdf`` field.
    2. A PDF named ``lesson.pdf`` or ``main.pdf`` (case-insensitive).
    3. First PDF alphabetically.
    """
    if not pdfs:
        return

    # Check metadata override
    override = metadata.get("primary_pdf", "").lower()
    if override:
        for pdf in pdfs:
            if pdf.filename.lower() == override:
                pdf.is_primary = True
                return

    # Check well-known names
    for pdf in pdfs:
        if pdf.filename.lower() in PRIMARY_PDF_NAMES:
            pdf.is_primary = True
            return

    # Fallback: first alphabetically (list is already sorted)
    pdfs[0].is_primary = True


# ── Enrichment helpers (thin wrappers around media.py) ──────────────────────

from mediastudyshelf.content.media import clear_cache, get_media_duration, get_pdf_page_count

_get_pdf_pages = get_pdf_page_count
_get_duration = get_media_duration

# ── Walking logic ───────────────────────────────────────────────────────────


def _natural_key(s: str) -> list[int | str]:
    """Split a string into a list of str/int chunks for natural sorting."""
    parts: list[int | str] = []
    for piece in re.split(r"(\d+)", s):
        if piece.isdigit():
            parts.append(int(piece))
        else:
            parts.append(piece.lower())
    return parts


def _sort_key(item: tuple[int | None, str]) -> tuple[int, list[int | str]]:
    """Sort by numeric prefix first (missing prefix sorts last), then natural."""
    order, name = item
    return (order if order is not None else 9999, _natural_key(name))


def walk_class(class_path: Path) -> ClassNode:
    """Build a ClassNode from a single class folder."""
    folder_name = class_path.name
    order, title = parse_folder_name(folder_name)
    slug = slug_from_name(folder_name)

    metadata = _load_json(class_path / "class.json")
    title = metadata.get("title", title)

    videos: list[FileEntry] = []
    pdfs: list[FileEntry] = []
    audio: list[FileEntry] = []
    extras: list[FileEntry] = []

    for entry in sorted(class_path.iterdir(), key=lambda e: (_natural_key(e.stem), e.suffix.lower())):
        if entry.is_dir() or entry.name.endswith(".json"):
            continue
        category = classify_file(entry.name)
        fe = FileEntry(
            filename=entry.name,
            category=category,
            path=entry,
            size_bytes=entry.stat().st_size,
            label=file_display_name(entry.name),
        )
        # Enrich with metadata from actual file contents
        if category == "pdf":
            fe.pages = _get_pdf_pages(entry)
        elif category in ("video", "audio"):
            fe.duration_seconds = _get_duration(entry)

        if category == "video":
            videos.append(fe)
        elif category == "pdf":
            pdfs.append(fe)
        elif category == "audio":
            audio.append(fe)
        else:
            extras.append(fe)

    # Primary video = first alphabetically
    if videos:
        videos[0].is_primary = True

    _resolve_primary_pdf(pdfs, metadata)

    # Apply audio labels from class.json metadata
    audio_labels = metadata.get("audio_labels", {})
    for a in audio:
        if a.filename in audio_labels:
            a.label = audio_labels[a.filename]

    return ClassNode(
        slug=slug,
        title=title,
        order=order,
        path=class_path,
        videos=videos,
        pdfs=pdfs,
        audio=audio,
        extras=extras,
    )


def walk_module(module_path: Path) -> ModuleNode:
    """Build a ModuleNode by walking its class subdirectories."""
    folder_name = module_path.name
    order, title = parse_folder_name(folder_name)
    slug = slug_from_name(folder_name)

    metadata = _load_json(module_path / "module.json")
    title = metadata.get("title", title)

    classes: list[ClassNode] = []
    for entry in module_path.iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            classes.append(walk_class(entry))

    classes.sort(key=lambda c: _sort_key((c.order, c.slug)))

    return ModuleNode(slug=slug, title=title, order=order, path=module_path, classes=classes)


def walk_course(course_path: Path) -> CourseNode:
    """Build a CourseNode by walking its module subdirectories."""
    folder_name = course_path.name
    order, title = parse_folder_name(folder_name)
    slug = slug_from_name(folder_name)

    metadata = _load_json(course_path / "course.json")
    title = metadata.get("title", title)

    modules: list[ModuleNode] = []
    for entry in course_path.iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            modules.append(walk_module(entry))

    modules.sort(key=lambda m: _sort_key((m.order, m.slug)))

    return CourseNode(
        slug=slug, title=title, order=order, path=course_path, modules=modules, metadata=metadata
    )


def walk_content(content_dir: str | Path) -> list[CourseNode]:
    """Walk a content root directory and return a list of courses."""
    clear_cache()
    root = Path(content_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Content directory not found: {root}")

    courses: list[CourseNode] = []
    for entry in root.iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            courses.append(walk_course(entry))

    courses.sort(key=lambda c: _sort_key((c.order, c.slug)))
    return courses
