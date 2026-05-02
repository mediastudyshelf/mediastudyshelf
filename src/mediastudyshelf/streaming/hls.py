"""Session-based HLS streaming with playhead-aware buffer management.

Each viewing session gets its own ffmpeg process that encodes in 60s chunks.
The frontend reports playhead position via heartbeat; the server spawns/kills
ffmpeg as needed. Sessions without heartbeat are cleaned up automatically.

Codec detection: if source is already H.264/AAC, uses -c copy (transmux).
Otherwise re-encodes to H.264/AAC for universal browser compatibility.
"""

import asyncio
import json
import logging
import os
import shutil
import signal
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

ENCODE_CHUNK = 60  # seconds of content per ffmpeg run
BUFFER_THRESHOLD = 30  # respawn when playhead is within this many seconds of end
HEARTBEAT_TIMEOUT = 60  # seconds without heartbeat before cleanup
SWEEP_INTERVAL = 15  # seconds between cleanup sweeps
SEGMENT_DURATION = 10  # HLS segment length in seconds

FPS_DEFAULT = 24

# ── Codec detection ──────────────────────────────────────────────────────


def probe_media(media_path: Path) -> tuple[str | None, str | None, float, None | float]:
    """Return (video_codec, audio_codec, duration_seconds, fps).

    Returns (None, None, 0.0, FPS_DEFAULT) on failure.
    For audio-only files, video_codec will be None.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(media_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        video_codec = None
        audio_codec = None
        fps = FPS_DEFAULT
        for s in streams:
            if s.get("codec_type") == "video" and not video_codec:
                video_codec = s.get("codec_name")

                # Parse FPS safely
                r = s.get("r_frame_rate", f"{FPS_DEFAULT}/1")
                try:
                    num, den = r.split("/")
                    fps = float(num) / float(den)
                except Exception:
                    pass
            elif s.get("codec_type") == "audio" and not audio_codec:
                audio_codec = s.get("codec_name")
        duration = float(data.get("format", {}).get("duration", 0))
        return video_codec, audio_codec, duration, fps
    except Exception as exc:
        logger.warning("probe_media failed for %s: %s", media_path, exc)
        return None, None, 0.0, FPS_DEFAULT


def _can_copy(video_codec: str | None, audio_codec: str | None) -> bool:
    """Return True if source codecs are HLS-compatible (no re-encode needed)."""
    return video_codec == "h264" and audio_codec in ("aac", None)


# ── Playlist parsing ─────────────────────────────────────────────────────


def _parse_playlist_duration(playlist_path: Path) -> float:
    """Parse an m3u8 playlist and return total duration in seconds."""
    if not playlist_path.is_file():
        return 0.0
    total = 0.0
    for line in playlist_path.read_text().splitlines():
        if line.startswith("#EXTINF:"):
            try:
                total += float(line.split(":")[1].rstrip(","))
            except (ValueError, IndexError):
                pass
    return total


def _generate_virtual_playlist(
    playlist_path: Path, total_duration: float, segment_duration: int = SEGMENT_DURATION,
) -> None:
    """Write a complete m3u8 with estimated segments covering the full video."""
    import math
    num_segments = math.ceil(total_duration / segment_duration)
    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        f"#EXT-X-TARGETDURATION:{segment_duration}",
        "#EXT-X-MEDIA-SEQUENCE:0",
        "#EXT-X-PLAYLIST-TYPE:VOD",
    ]
    for i in range(num_segments):
        remaining = total_duration - i * segment_duration
        dur = min(segment_duration, remaining)
        lines.append(f"#EXTINF:{dur:.6f},")
        lines.append(f"segments/seg_{i:04d}.ts")
    lines.append("#EXT-X-ENDLIST")
    lines.append("")
    playlist_path.write_text("\n".join(lines))


# ── Session ──────────────────────────────────────────────────────────────


@dataclass
class Session:
    id: str
    media_path: Path  # Path to media file (video or audio)
    hls_dir: Path
    use_copy: bool  # True = transmux, False = re-encode
    total_duration: float = 0.0  # full media length in seconds
    process: subprocess.Popen | None = None
    paused: bool = False  # True when SIGSTOP'd
    last_heartbeat: float = field(default_factory=time.monotonic)
    playhead: float = 0.0
    encode_start: float = 0.0  # absolute time in media where encoding started
    fps: float = FPS_DEFAULT
    is_audio_only: bool = False  # True for audio-only files

    @property
    def playlist_path(self) -> Path:
        """Virtual playlist served to HLS.js (full duration, ENDLIST)."""
        return self.hls_dir / "playlist.m3u8"

    @property
    def internal_playlist_path(self) -> Path:
        """ffmpeg's working playlist (not served to client)."""
        return self.hls_dir / "_internal.m3u8"

    @property
    def _active_playlist(self) -> Path:
        """The playlist ffmpeg is writing to."""
        return self.playlist_path if self.use_copy else self.internal_playlist_path

    @property
    def encoded_up_to(self) -> float:
        """How far into the video we have segments for."""
        return self.encode_start + _parse_playlist_duration(self._active_playlist)

    @property
    def is_alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def is_fully_encoded(self) -> bool:
        return self.total_duration > 0 and self.encoded_up_to >= self.total_duration - 1


# ── Session Manager ──────────────────────────────────────────────────────


class SessionManager:
    def __init__(self, cache_dir: Path):
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, Session] = {}

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    def create(self, media_path: Path) -> tuple[str, str]:
        """Create a new streaming session. Returns (session_id, hls_url)."""
        session_id = uuid.uuid4().hex[:16]
        hls_dir = self._cache_dir / session_id
        hls_dir.mkdir(parents=True, exist_ok=True)
        (hls_dir / "segments").mkdir(exist_ok=True)

        video_codec, audio_codec, duration, fps = probe_media(media_path)
        # use_copy = _can_copy(video_codec, audio_codec)
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
        self._spawn_ffmpeg(session, start_time=0.0)
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

    def sweep_expired(self) -> None:
        """Remove expired sessions and finalize completed ones."""
        now = time.monotonic()
        for session in list(self._sessions.values()):
            if now - session.last_heartbeat > HEARTBEAT_TIMEOUT:
                logger.info("Session %s expired (no heartbeat)", session.id)
                self.cleanup(session.id)

    # ── Playlist helpers ─────────────────────────────────────────

    def _wait_for_buffer(self, session: Session, timeout: float = 60) -> None:
        """Block until initial buffer is ready, then pause ffmpeg."""
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
        """Spawn a single ffmpeg process for the full media from start_time."""
        if session.is_alive:
            return

        session.encode_start = start_time

        gop = int(session.fps * SEGMENT_DURATION)
        aligned_start = (start_time // SEGMENT_DURATION) * SEGMENT_DURATION
        segment_index = int(aligned_start // SEGMENT_DURATION)

        cmd = ["ffmpeg", "-y"]

        if start_time > 0:
            cmd += ["-ss", str(aligned_start)]

        cmd += [
            "-fflags", "+genpts",
            "-readrate", "5",
            "-i", str(session.media_path),
            "-output_ts_offset", str(aligned_start),
            "-start_number", str(segment_index),
        ]

        if session.use_copy:
            cmd += ["-c", "copy"]
            # Copy mode: write real playlist directly (accurate durations)
            output_playlist = session.playlist_path
        elif session.is_audio_only:
            # Audio-only: no video codec, just audio to AAC
            cmd += [
                "-vn",  # no video
                "-c:a", "aac",
                "-b:a", "128k",
                "-ac", "2",
            ]
            output_playlist = session.internal_playlist_path
        else:
            # Video re-encode mode
            cmd += [
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",

                # CRITICAL: deterministic segmentation
                "-g", str(gop),
                "-keyint_min", str(gop),
                "-sc_threshold", "0",
                # align keyframes exactly to segment boundaries
                "-force_key_frames", f"expr:gte(t,n_forced*{SEGMENT_DURATION})",

                "-c:a", "aac",
                "-b:a", "128k",
                "-ac", "2",
            ]
            # Re-encode mode: write to internal playlist (virtual one is served)
            output_playlist = session.internal_playlist_path

        cmd += [
            "-hls_time", str(SEGMENT_DURATION),
            "-hls_list_size", "0",
            "-hls_segment_filename", str(session.hls_dir / "segments" / "seg_%04d.ts"),
            "-f", "hls",
            str(output_playlist),
        ]

        try:
            session.process = subprocess.Popen(
                cmd,
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


# ── Module-level manager (set from main.py) ──────────────────────────────

_manager: SessionManager | None = None


def get_manager() -> SessionManager:
    assert _manager is not None, "SessionManager not initialized"
    return _manager


def set_manager(manager: SessionManager) -> None:
    global _manager
    _manager = manager


async def sweep_loop() -> None:
    """Background task that periodically cleans up expired sessions."""
    while True:
        await asyncio.sleep(SWEEP_INTERVAL)
        if _manager:
            _manager.sweep_expired()
