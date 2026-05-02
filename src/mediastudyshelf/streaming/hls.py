"""HLS primitives — codec probing, playlist construction, the ``Session`` value
type, and the module-level ``SessionManager`` singleton plus the GC loop that
runs on top of it.

Imported by ``session_manager.py`` (one-way dependency) and by ``main.py`` for
the singleton wiring. ``SessionManager`` itself lives in ``session_manager.py``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mediastudyshelf.streaming.session_manager import SessionManager

logger = logging.getLogger(__name__)

ENCODE_CHUNK = 60  # seconds of content per ffmpeg run
BUFFER_THRESHOLD = 30  # respawn when playhead is within this many seconds of end
HEARTBEAT_TIMEOUT = 60  # seconds without heartbeat before cleanup
SESSION_GC_INTERVAL = 15  # seconds between session GC passes
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


# ── Module-level manager (set from main.py) ──────────────────────────────

_manager: SessionManager | None = None


def get_manager() -> SessionManager:
    assert _manager is not None, "SessionManager not initialized"
    return _manager


def set_manager(manager: SessionManager) -> None:
    global _manager
    _manager = manager


async def session_gc_loop() -> None:
    """Background task that periodically cleans up expired sessions."""
    while True:
        await asyncio.sleep(SESSION_GC_INTERVAL)
        if _manager:
            _manager.gc_expired()
