"""HTTP API package — composes the /api router from per-feature sub-modules.

``router`` carries every JSON endpoint mounted at /api.
``media_router`` carries binary HLS serving mounted at /media.
``set_courses`` is the startup/reload hook that injects the walked tree.
"""

from __future__ import annotations

from fastapi import APIRouter

from mediastudyshelf.api import class_view, stream, tree
from mediastudyshelf.api.state import set_courses

router = APIRouter(prefix="/api")
router.include_router(tree.router)
router.include_router(class_view.router)
router.include_router(stream.router)

media_router = stream.media_router

__all__ = ["router", "media_router", "set_courses"]
