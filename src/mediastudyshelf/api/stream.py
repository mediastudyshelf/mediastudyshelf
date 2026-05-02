"""Streaming endpoints.

Two routers live here:

- ``router`` — JSON control surface mounted under ``/api`` (prepare/heartbeat).
- ``media_router`` — binary HLS playlist/segment serving mounted under ``/media``.
  Kept on a separate prefix so static media URLs never collide with JSON APIs.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from mediastudyshelf.api.state import get_content_root
from mediastudyshelf.streaming import get_manager

logger = logging.getLogger(__name__)


# ── Models ─────────────────────────────────────────────────────────────────


class StreamPrepareRequest(BaseModel):
    media_url: str  # /media/assets/... path (video or audio)


class StreamPrepareResponse(BaseModel):
    url: str
    id: str


class StreamHeartbeatRequest(BaseModel):
    time: float  # playhead position in seconds


# ── /api/stream — control plane ────────────────────────────────────────────

router = APIRouter()


@router.post("/stream/prepare", response_model=StreamPrepareResponse)
async def stream_prepare(body: StreamPrepareRequest):
    """Create a streaming session for a video or audio file."""
    if not body.media_url.startswith("/media/assets/"):
        raise HTTPException(status_code=400, detail="Invalid media URL")
    rel = body.media_url[len("/media/assets/"):]
    media_path = get_content_root() / rel

    if not media_path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")

    session_id, url = await asyncio.to_thread(get_manager().create, media_path)
    return StreamPrepareResponse(url=url, id=session_id)


@router.post("/stream/{session_id}/heartbeat")
async def stream_heartbeat(session_id: str, body: StreamHeartbeatRequest):
    """Report playhead position and keep session alive."""
    if not get_manager().heartbeat(session_id, body.time):
        raise HTTPException(status_code=404, detail="Streaming session not found")
    return {"status": "ok"}


# ── /media/stream — binary HLS serving ─────────────────────────────────────

media_router = APIRouter(prefix="/media")


@media_router.get("/stream/{session_id}/playlist.m3u8")
async def stream_playlist(session_id: str):
    """Serve HLS playlist for a streaming session."""
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


@media_router.get("/stream/{session_id}/segments/{segment}")
async def stream_segment(session_id: str, segment: str):
    """Serve HLS segment for a streaming session."""
    try:
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

        logger.info(f"Segment {segment} not ready for session {session_id}, starting ffmpeg if needed")

        # Segment not ready — resume ffmpeg if paused.
        if session.paused:
            logger.info(f"Resuming paused ffmpeg for session {session_id}")
            mgr._resume_ffmpeg(session)
        elif not session.is_alive and not session.is_fully_encoded:
            # ffmpeg not running and not finished — need to spawn it
            # Parse segment number from filename (seg_XXXX.ts)
            try:
                seg_num = int(segment.replace("seg_", "").replace(".ts", ""))
                start_time = seg_num * 10  # SEGMENT_DURATION = 10 seconds
            except ValueError:
                start_time = 0
            logger.info(f"Spawning ffmpeg for session {session_id} at {start_time}s")
            mgr._prepare_seek(session, new_start=start_time)
            mgr._spawn_ffmpeg(session, start_time=start_time)

        # Wait for the segment to appear
        for i in range(300):  # up to 30 seconds
            if seg_path.is_file() and seg_path.stat().st_size > 0:
                logger.info(f"Segment {segment} ready after {i*0.1:.1f}s")
                return FileResponse(str(seg_path), media_type="video/mp2t")
            await asyncio.sleep(0.1)

        logger.warning(f"Segment {segment} timeout for session {session_id}")
        raise HTTPException(status_code=404, detail="Segment not ready")
    except asyncio.CancelledError:
        logger.info(f"Client disconnected while waiting for segment {segment} in session {session_id}")
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error serving segment {segment} for session {session_id}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
