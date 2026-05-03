"""GET /api/tree — full course/module/class hierarchy."""

from __future__ import annotations

from fastapi import APIRouter

from mediastudyshelf.api.types import (
    ClassSummary,
    CourseSummary,
    ModuleSummary,
    TreeResponse,
)
from mediastudyshelf.core.state import get_courses

router = APIRouter()


@router.get("/tree", response_model=TreeResponse)
async def get_tree():
    return TreeResponse(
        courses=[
            CourseSummary(
                slug=course.slug,
                title=course.title,
                modules=[
                    ModuleSummary(
                        slug=module.slug,
                        title=module.title,
                        classes=[
                            ClassSummary(
                                slug=cls.slug,
                                title=cls.title,
                                order=ci,
                            )
                            for ci, cls in enumerate(module.classes, 1)
                        ],
                    )
                    for module in course.modules
                ],
            )
            for course in get_courses()
        ]
    )
