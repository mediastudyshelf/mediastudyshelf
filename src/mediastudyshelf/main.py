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
from mediastudyshelf.hls import SessionManager, set_manager, sweep_loop
from mediastudyshelf.routes import router, set_courses
from mediastudyshelf.walker import walk_content

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
        from mediastudyshelf.watcher import watch_content as watch_content_dir

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


@app.get("/health")
async def health():
    return {"status": "ok"}


# Static file mounts — must come BEFORE the SPA catch-all so they take priority.
app.mount("/media", StaticFiles(directory=str(get_content_path())), name="media")

if serve_frontend():
    _dist = get_frontend_dist()
    if _dist.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="frontend-assets")
        logger.info("Serving frontend from %s", _dist)
    else:
        logger.warning("SERVE_FRONTEND=1 but dist not found at %s", _dist)


# ── Dynamic HLS serving — waits for segments to be ready ─────────────────


@app.get("/hls/{session_id}/playlist.m3u8")
async def hls_playlist(session_id: str):
    from mediastudyshelf.hls import get_manager

    mgr = get_manager()
    session = mgr._sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.playlist_path.is_file():
        raise HTTPException(status_code=404, detail="Playlist not ready")

    return FileResponse(
        str(session.playlist_path),
        media_type="application/vnd.apple.mpegurl",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/hls/{session_id}/segments/{segment}")
async def hls_segment(session_id: str, segment: str):
    from mediastudyshelf.hls import get_manager

    mgr = get_manager()
    session = mgr._sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    seg_path = session.hls_dir / "segments" / segment
    if not segment.endswith(".ts"):
        raise HTTPException(status_code=400, detail="Invalid segment")

    # Serve immediately if ready
    if seg_path.is_file() and seg_path.stat().st_size > 0:
        return FileResponse(str(seg_path), media_type="video/mp2t")

    # Segment not ready — resume ffmpeg if paused and wait.
    # Do NOT trigger heartbeat/seek here — that's the frontend's job.
    # HLS.js prefetches segments at various positions; triggering seeks
    # from here causes cascading restarts.
    if session.paused:
        mgr._resume_ffmpeg(session)

    # Wait for the segment to appear
    for _ in range(300):  # up to 30 seconds
        if seg_path.is_file() and seg_path.stat().st_size > 0:
            return FileResponse(str(seg_path), media_type="video/mp2t")
        await asyncio.sleep(0.1)

    raise HTTPException(status_code=404, detail="Segment not ready")


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
