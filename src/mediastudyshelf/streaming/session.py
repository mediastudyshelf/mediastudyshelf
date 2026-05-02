"""``Session`` value type — one viewer's HLS streaming state."""

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from mediastudyshelf.streaming.constants import FPS_DEFAULT
from mediastudyshelf.streaming.playlist import _parse_playlist_duration


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
