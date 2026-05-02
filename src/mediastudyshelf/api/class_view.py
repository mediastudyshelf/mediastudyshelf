"""GET /api/class/{course}/{module}/{class} — single-class detail with prev/next nav."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from mediastudyshelf.api.state import get_courses, media_url
from mediastudyshelf.models import (
    AudioDetail,
    ClassDetail,
    ClassResponse,
    CourseRef,
    ExtraDetail,
    ModuleRef,
    NavItem,
    NavResponse,
    PdfDetail,
    VideoDetail,
)
from mediastudyshelf.content.walker import ClassNode, CourseNode, ModuleNode

router = APIRouter()


def _find_course(slug: str) -> CourseNode:
    for c in get_courses():
        if c.slug == slug:
            return c
    raise HTTPException(status_code=404, detail=f"Course not found: {slug}")


def _find_module(course: CourseNode, slug: str) -> tuple[ModuleNode, int]:
    for i, m in enumerate(course.modules):
        if m.slug == slug:
            return m, i + 1
    raise HTTPException(status_code=404, detail=f"Module not found: {slug}")


def _find_class(module: ModuleNode, slug: str) -> tuple[ClassNode, int]:
    for i, c in enumerate(module.classes):
        if c.slug == slug:
            return c, i + 1
    raise HTTPException(status_code=404, detail=f"Class not found: {slug}")


def _flatten_classes(course: CourseNode) -> list[tuple[ModuleNode, ClassNode]]:
    """Flatten all classes in a course into an ordered list of (module, class) tuples."""
    flat: list[tuple[ModuleNode, ClassNode]] = []
    for module in course.modules:
        for cls in module.classes:
            flat.append((module, cls))
    return flat


def _compute_nav(course: CourseNode, module: ModuleNode, cls: ClassNode) -> NavResponse:
    """Compute prev/next navigation for a class."""
    flat = _flatten_classes(course)
    idx = next(i for i, (_, c) in enumerate(flat) if c is cls)

    prev_item = None
    if idx > 0:
        prev_mod, prev_cls = flat[idx - 1]
        prev_item = NavItem(
            course=course.slug,
            module=prev_mod.slug,
            class_slug=prev_cls.slug,
            title=prev_cls.title,
        )

    next_item = None
    if idx < len(flat) - 1:
        next_mod, next_cls = flat[idx + 1]
        next_item = NavItem(
            course=course.slug,
            module=next_mod.slug,
            class_slug=next_cls.slug,
            title=next_cls.title,
        )

    return NavResponse(prev=prev_item, next=next_item)


@router.get(
    "/class/{course_slug}/{module_slug}/{class_slug}",
    response_model=ClassResponse,
    response_model_by_alias=True,
)
async def get_class(course_slug: str, module_slug: str, class_slug: str):
    course = _find_course(course_slug)
    module, module_number = _find_module(course, module_slug)
    cls, class_number = _find_class(module, class_slug)

    videos = [
        VideoDetail(
            filename=v.filename,
            url=media_url(v.path),
            duration_seconds=v.duration_seconds,
            is_primary=v.is_primary,
        )
        for v in cls.videos
    ]

    pdfs = [
        PdfDetail(
            filename=pdf.filename,
            url=media_url(pdf.path),
            pages=pdf.pages,
            size_bytes=pdf.size_bytes,
            is_primary=pdf.is_primary,
        )
        for pdf in cls.pdfs
    ]

    audio = [
        AudioDetail(
            filename=a.filename,
            label=a.label,
            url=media_url(a.path),
            duration_seconds=a.duration_seconds,
        )
        for a in cls.audio
    ]

    extras = [
        ExtraDetail(
            filename=e.filename,
            url=media_url(e.path),
            size_bytes=e.size_bytes,
        )
        for e in cls.extras
    ]

    nav = _compute_nav(course, module, cls)

    return ClassResponse(
        course=CourseRef(slug=course.slug, title=course.title),
        module=ModuleRef(slug=module.slug, title=module.title, number=module_number),
        class_detail=ClassDetail(
            slug=cls.slug,
            title=cls.title,
            number=class_number,
            videos=videos,
            pdfs=pdfs,
            audio=audio,
            extras=extras,
        ),
        nav=nav,
    )
