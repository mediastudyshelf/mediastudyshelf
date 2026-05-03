"""Core domain types — re-exported for ergonomic imports.

Consumers do ``from mediastudyshelf.core.types import CourseNode`` rather
than reaching into submodules. Add new type modules here when they appear;
keep the wildcard list explicit so the package's surface is auditable.
"""

from mediastudyshelf.core.types.content import (
    ClassNode,
    CourseNode,
    FileEntry,
    ModuleNode,
)

__all__ = [
    "ClassNode",
    "CourseNode",
    "FileEntry",
    "ModuleNode",
]
