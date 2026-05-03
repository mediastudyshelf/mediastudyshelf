"""Pydantic shapes for ``GET /api/tree``."""

from pydantic import BaseModel


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
