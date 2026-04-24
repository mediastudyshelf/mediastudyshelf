"""Pydantic response models matching the API shape in SPEC.md §5."""

from pydantic import BaseModel, Field


# ── /api/tree models ────────────────────────────────────────────────────────


class ClassSummary(BaseModel):
    slug: str
    title: str
    order: int


class ModuleSummary(BaseModel):
    slug: str
    title: str
    classes: list[ClassSummary]


class CourseSummary(BaseModel):
    slug: str
    title: str
    modules: list[ModuleSummary]


class TreeResponse(BaseModel):
    courses: list[CourseSummary]


# ── /api/class models ──────────────────────────────────────────────────────


class CourseRef(BaseModel):
    slug: str
    title: str


class ModuleRef(BaseModel):
    slug: str
    title: str
    number: int


class VideoDetail(BaseModel):
    url: str
    duration_seconds: int | None


class PdfDetail(BaseModel):
    filename: str
    url: str
    pages: int | None
    size_bytes: int
    is_primary: bool


class AudioDetail(BaseModel):
    filename: str
    label: str
    url: str
    duration_seconds: int | None


class ExtraDetail(BaseModel):
    filename: str
    url: str
    size_bytes: int


class NavItem(BaseModel):
    course: str
    module: str
    class_slug: str = Field(serialization_alias="class")
    title: str


class NavResponse(BaseModel):
    prev: NavItem | None
    next: NavItem | None


class ClassDetail(BaseModel):
    slug: str
    title: str
    number: int
    video: VideoDetail | None
    pdfs: list[PdfDetail]
    audio: list[AudioDetail]
    extras: list[ExtraDetail]


class ClassResponse(BaseModel):
    course: CourseRef
    module: ModuleRef
    class_detail: ClassDetail = Field(serialization_alias="class")
    nav: NavResponse
