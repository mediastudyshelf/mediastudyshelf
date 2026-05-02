import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

from mediastudyshelf.config import (
    get_content_path,
    get_frontend_dist,
    get_hls_cache_path,
    serve_frontend,
    watch_enabled,
)
from mediastudyshelf.api import router, media_router, set_courses
from mediastudyshelf.content.walker import walk_content
from mediastudyshelf.streaming.hls import SessionManager, set_manager, sweep_loop

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    hls_cache = get_hls_cache_path()
    manager = SessionManager(hls_cache)
    set_manager(manager)

    content_path = get_content_path()
    courses = walk_content(content_path)
    set_courses(courses, content_path)

    sweep_task = asyncio.create_task(sweep_loop())

    watcher_task = None
    if watch_enabled():
        from mediastudyshelf.content.watcher import watch_content as watch_content_dir

        watcher_task = asyncio.create_task(watch_content_dir(content_path))
        logger.info("Filesystem watcher enabled for %s", content_path)

    yield

    sweep_task.cancel()
    if watcher_task is not None:
        watcher_task.cancel()
    for task in [sweep_task, watcher_task]:
        if task is not None:
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="MediaStudyShelf", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.include_router(media_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Static file mounts — must come BEFORE the SPA catch-all so they take priority.
# Content files are now under /media/assets/*
app.mount("/media/assets", StaticFiles(directory=str(get_content_path())), name="media-assets")

if serve_frontend():
    _dist = get_frontend_dist()
    if _dist.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="frontend-assets")
        logger.info("Serving frontend from %s", _dist)
    else:
        logger.warning("SERVE_FRONTEND=1 but dist not found at %s", _dist)


# Note: Dynamic streaming endpoints moved to media_router in routes.py


# SPA fallback — must be registered last so /api/*, /media/*, /assets/* take priority.
# Catches all unmatched GET requests and serves index.html for client-side routing.
@app.get("/{full_path:path}")
async def spa_fallback(request: Request, full_path: str):
    if not serve_frontend():
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not found"}, status_code=404)

    index = get_frontend_dist() / "index.html"
    if index.is_file():
        return FileResponse(str(index), media_type="text/html")

    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": "Frontend not built"}, status_code=404)


def main() -> None:
    """Console-script entrypoint — launches the FastAPI app with uvicorn."""
    import uvicorn

    uvicorn.run(
        "mediastudyshelf.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
