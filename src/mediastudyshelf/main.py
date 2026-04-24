import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

from mediastudyshelf.config import (
    get_content_path,
    get_frontend_dist,
    serve_frontend,
    watch_enabled,
)
from mediastudyshelf.routes import router, set_courses
from mediastudyshelf.walker import walk_content

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    content_path = get_content_path()
    courses = walk_content(content_path)
    set_courses(courses, content_path)
    app.mount("/media", StaticFiles(directory=str(content_path)), name="media")

    if serve_frontend():
        dist = get_frontend_dist()
        if dist.is_dir():
            # Serve hashed JS/CSS/assets — must come after /api and /media
            app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="frontend-assets")
            logger.info("Serving frontend from %s", dist)
        else:
            logger.warning("SERVE_FRONTEND=1 but dist not found at %s", dist)

    watcher_task = None
    if watch_enabled():
        from mediastudyshelf.watcher import watch_content as watch_content_dir

        watcher_task = asyncio.create_task(watch_content_dir(content_path))
        logger.info("Filesystem watcher enabled for %s", content_path)

    yield

    if watcher_task is not None:
        watcher_task.cancel()
        try:
            await watcher_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="MediaStudyShelf", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}


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
