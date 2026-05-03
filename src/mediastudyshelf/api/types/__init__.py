"""HTTP request/response shapes — re-exported for ergonomic imports.

Subdivided by route family. Consumers do
``from mediastudyshelf.api.types import ClassResponse`` rather than reaching
into submodules.

Note: these are HTTP-shaped pydantic models (with serialization aliases like
``class_`` → ``class``). Domain types live in
``mediastudyshelf.core.types``; this package is the boundary translation.
"""

from mediastudyshelf.api.types.class_view import (
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
from mediastudyshelf.api.types.stream import (
    StreamHeartbeatRequest,
    StreamPrepareRequest,
    StreamPrepareResponse,
)
from mediastudyshelf.api.types.tree import (
    ClassSummary,
    CourseSummary,
    ModuleSummary,
    TreeResponse,
)

__all__ = [
    # class_view
    "AudioDetail",
    "ClassDetail",
    "ClassResponse",
    "CourseRef",
    "ExtraDetail",
    "ModuleRef",
    "NavItem",
    "NavResponse",
    "PdfDetail",
    "VideoDetail",
    # stream
    "StreamHeartbeatRequest",
    "StreamPrepareRequest",
    "StreamPrepareResponse",
    # tree
    "ClassSummary",
    "CourseSummary",
    "ModuleSummary",
    "TreeResponse",
]
