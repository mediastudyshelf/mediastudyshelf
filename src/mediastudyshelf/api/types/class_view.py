"""Pydantic shapes for ``GET /api/class/{course}/{module}/{class}``."""

from pydantic import BaseModel, Field


class CourseRef(BaseModel):
    slug: str
    title: str


class ModuleRef(BaseModel):
    slug: str
    title: str
    number: int


class VideoDetail(BaseModel):
    filename: str
    url: str
    duration_seconds: int | None
    is_primary: bool


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
    videos: list[VideoDetail]
    pdfs: list[PdfDetail]
    audio: list[AudioDetail]
    extras: list[ExtraDetail]


class ClassResponse(BaseModel):
    course: CourseRef
    module: ModuleRef
    class_detail: ClassDetail = Field(serialization_alias="class")
    nav: NavResponse
