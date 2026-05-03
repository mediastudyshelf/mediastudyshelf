"""SessionManager — per-viewer HLS session lifecycle.

Owns the active ``Session`` map and the ffmpeg process attached to each one.
Public surface:

- ``create(media_path)`` — start a new session and return ``(id, hls_url)``.
- ``heartbeat(id, playhead)`` — refresh the watchdog and steer ffmpeg
  (pause/resume/seek) based on how far ahead the buffer is.
- ``cleanup(id)`` — kill ffmpeg and wipe the session's scratch directory.
- ``gc_expired()`` — single GC pass: cleanup sessions with stale heartbeats.

Codec detection: if source is already H.264/AAC, uses ``-c copy`` (transmux).
Otherwise re-encodes to H.264/AAC for universal browser compatibility.
"""

from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

from mediastudyshelf.core.stream.constants import (
    BUFFER_THRESHOLD,
    ENCODE_CHUNK,
    FPS_DEFAULT,
    HEARTBEAT_TIMEOUT,
    SEGMENT_DURATION,
)
from mediastudyshelf.core.stream.encoders import encoder_for
from mediastudyshelf.core.stream.playlist import _generate_virtual_playlist
from mediastudyshelf.core.stream.probe import probe_media
from mediastudyshelf.core.stream.session import Session

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self, cache_dir: Path):
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, Session] = {}

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    def create(self, media_path: Path, start_time: float = 0.0) -> tuple[str, str]:
        """Create a new streaming session.

        ``start_time`` lets the caller (e.g. resume-from-pause) seek ffmpeg to a
        specific timestamp at session creation, so ``_wait_for_buffer`` warms up
        segments around the resume point instead of from t=0.

        Returns (session_id, hls_url).
        """
        session_id = uuid.uuid4().hex[:16]
        hls_dir = self._cache_dir / session_id
        hls_dir.mkdir(parents=True, exist_ok=True)
        (hls_dir / "segments").mkdir(exist_ok=True)

        video_codec, audio_codec, duration, fps = probe_media(media_path)
        # use_copy = can_copy(video_codec, audio_codec)
        use_copy = False
        is_audio_only = video_codec is None and audio_codec is not None

        session = Session(
            id=session_id,
            media_path=media_path,
            hls_dir=hls_dir,
            use_copy=use_copy,
            total_duration=duration,
            fps=fps if not is_audio_only else FPS_DEFAULT,
            is_audio_only=is_audio_only,
        )
        self._sessions[session_id] = session

        media_type = "audio" if is_audio_only else "video"
        logger.info(
            "Session %s created for %s (type: %s, mode: %s, duration: %.1fs)",
            session_id, media_path.name, media_type,
            "copy" if use_copy else "re-encode", duration,
        )

        if not use_copy:
            _generate_virtual_playlist(session.playlist_path, duration)
        self._spawn_ffmpeg(session, start_time=start_time)
        self._wait_for_buffer(session)
        session.last_heartbeat = time.monotonic()
        return session_id, f"/media/stream/{session_id}/playlist.m3u8"

    def heartbeat(self, session_id: str, playhead: float) -> bool:
        """Update session heartbeat and manage buffer via SIGSTOP/SIGCONT."""
        session = self._sessions.get(session_id)
        if session is None:
            return False

        # Session was cleaned up externally
        if not session.hls_dir.is_dir():
            self._sessions.pop(session_id, None)
            return False

        session.last_heartbeat = time.monotonic()
        session.playhead = playhead

        encoded_end = session.encoded_up_to

        # Check if the segment for the current playhead exists on disk
        target_seg = int(playhead // SEGMENT_DURATION)
        target_file = session.hls_dir / "segments" / f"seg_{target_seg:04d}.ts"
        segment_exists = target_file.is_file()

        # Seek detection: always on backward seek, or forward when segment missing
        is_backward = playhead < session.encode_start
        is_seek = is_backward or not segment_exists
        if is_seek:
            logger.info(
                "Session %s: seek detected (playhead=%.1f, buffered=%.1f-%.1f)",
                session_id, playhead, session.encode_start, encoded_end,
            )
            self._kill_ffmpeg(session)
            self._prepare_seek(session, new_start=playhead)
            self._spawn_ffmpeg(session, start_time=playhead)
            return True

        # Eager-encode sessions skip buffer management — ffmpeg runs to
        # completion regardless of how far ahead of the playhead we are.
        if encoder_for(session).eager_encode:
            return True

        # Buffer management: pause/resume ffmpeg based on playhead
        if session.is_alive:
            buffer_ahead = encoded_end - playhead
            if buffer_ahead > ENCODE_CHUNK and not session.paused:
                # Far enough ahead — pause ffmpeg to save CPU/disk
                self._pause_ffmpeg(session)
            elif buffer_ahead <= BUFFER_THRESHOLD and session.paused:
                # Running low — resume ffmpeg
                self._resume_ffmpeg(session)
        elif not segment_exists and not session.is_fully_encoded:
            # ffmpeg not running but segment needed — spawn from this position
            logger.info(
                "Session %s: segment %d missing, spawning from %.1fs",
                session_id, target_seg, playhead,
            )
            self._prepare_seek(session, new_start=playhead)
            self._spawn_ffmpeg(session, start_time=playhead)

        return True

    def cleanup(self, session_id: str) -> bool:
        """Kill ffmpeg and remove session data."""
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False

        self._kill_ffmpeg(session)
        if session.hls_dir.is_dir():
            shutil.rmtree(session.hls_dir)
        logger.info("Session %s cleaned up", session.id)
        return True

    def gc_expired(self) -> None:
        """Remove expired sessions and finalize completed ones."""
        now = time.monotonic()
        for session in list(self._sessions.values()):
            if now - session.last_heartbeat > HEARTBEAT_TIMEOUT:
                logger.info("Session %s expired (no heartbeat)", session.id)
                self.cleanup(session.id)

    # ── Playlist helpers ─────────────────────────────────────────

    def _wait_for_buffer(self, session: Session, timeout: float = 60) -> None:
        """Block until initial buffer is ready, then pause ffmpeg.

        For sessions whose encoder spec is ``eager_encode=True`` we skip the
        pause step and let ffmpeg run to completion in the background — the
        per-mode policy in ``encoders.py`` decides this.
        """
        deadline = time.monotonic() + timeout

        # Phase 1: wait for at least one segment
        playlist = session._active_playlist
        while time.monotonic() < deadline:
            if playlist.is_file():
                content = playlist.read_text()
                if "#EXTINF:" in content:
                    break
            time.sleep(0.1)
        else:
            logger.warning("Session %s: timed out waiting for first segment", session.id)
            return

        if encoder_for(session).eager_encode:
            logger.info("Session %s: eager-encode mode, ffmpeg runs to completion", session.id)
            return

        # Phase 2: let buffer build to ENCODE_CHUNK, then pause
        while time.monotonic() < deadline and session.is_alive:
            if session.encoded_up_to - session.encode_start >= ENCODE_CHUNK:
                self._pause_ffmpeg(session)
                return
            time.sleep(0.1)

        # ffmpeg finished before reaching buffer target (short video) — that's fine
        logger.info("Session %s: initial buffer ready (%.1fs encoded)", session.id, session.encoded_up_to)

    # ── ffmpeg process management ────────────────────────────────

    def _spawn_ffmpeg(self, session: Session, start_time: float) -> None:
        """Spawn ffmpeg for this session. The full command is built by the
        per-mode spec in ``encoders.py``; this method only owns the process
        lifecycle (spawn + bookkeeping)."""
        if session.is_alive:
            return

        session.encode_start = start_time
        spec = encoder_for(session).build_spec(start_time)

        try:
            session.process = subprocess.Popen(
                spec.cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            session.paused = False
            logger.info(
                "Session %s: ffmpeg started from %.1fs (pid %d)",
                session.id, start_time, session.process.pid,
            )
        except FileNotFoundError:
            logger.error("ffmpeg not found")
            session.process = None

    def _pause_ffmpeg(self, session: Session) -> None:
        """Pause ffmpeg with SIGSTOP (freeze, no CPU)."""
        if not session.is_alive or session.paused:
            return
        try:
            os.kill(session.process.pid, signal.SIGSTOP)
            session.paused = True
            logger.info("Session %s: ffmpeg paused (pid %d)", session.id, session.process.pid)
        except ProcessLookupError:
            session.process = None

    def _resume_ffmpeg(self, session: Session) -> None:
        """Resume ffmpeg with SIGCONT."""
        if not session.is_alive or not session.paused:
            return
        try:
            os.kill(session.process.pid, signal.SIGCONT)
            session.paused = False
            logger.info("Session %s: ffmpeg resumed (pid %d)", session.id, session.process.pid)
        except ProcessLookupError:
            session.process = None

    def _kill_ffmpeg(self, session: Session) -> None:
        """Terminate the ffmpeg process and reap it."""
        if session.process is None:
            return
        pid = session.process.pid
        # Resume first if paused (SIGTERM on a stopped process may not work)
        if session.paused:
            try:
                os.kill(pid, signal.SIGCONT)
            except ProcessLookupError:
                pass
        # If already exited, just reap
        if session.process.poll() is not None:
            try:
                session.process.wait(timeout=1)
            except Exception:
                pass
            session.process = None
            session.paused = False
            return
        # Kill it
        try:
            os.kill(pid, signal.SIGTERM)
            try:
                session.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.kill(pid, signal.SIGKILL)
                session.process.wait(timeout=5)
        except ProcessLookupError:
            pass
        logger.info("Session %s: ffmpeg killed (pid %d)", session.id, pid)
        session.process = None
        session.paused = False

    def _prepare_seek(self, session: Session, new_start: float) -> None:
        """Delete all segments and reset ffmpeg state for a fresh start."""
        seg_dir = session.hls_dir / "segments"
        if seg_dir.is_dir():
            for f in seg_dir.iterdir():
                f.unlink()

        if session.internal_playlist_path.is_file():
            session.internal_playlist_path.unlink()
        if session.use_copy and session.playlist_path.is_file():
            session.playlist_path.unlink()

        session.encode_start = new_start
