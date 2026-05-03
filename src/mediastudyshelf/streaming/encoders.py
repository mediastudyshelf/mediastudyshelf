"""Per-mode encoders.

Each encoder class owns the full ffmpeg invocation for one streaming mode.
``EncoderBase`` defines the shared shape — input args, HLS output args, and
``build_spec`` which composes them with codec-specific flags. Subclasses
override ``_codec_args`` (and optionally ``output_playlist`` /
``eager_encode``) to express their mode.

The manager only sees ``EncoderSpec`` — a frozen ``(cmd, output_playlist,
eager_encode)`` tuple — and never touches ffmpeg flags directly.

Extension points:

- New mode → subclass ``EncoderBase``, add a dispatch case in ``encoder_for``.
- Swap ffmpeg for another tool → override ``_input_args`` / ``_hls_output_args``
  on a sibling base class (or replace ``EncoderBase`` wholesale if the new
  tool isn't a CLI process at all).
- Encoding profiles → either pass tunables into ``__init__`` (cheap, when
  profiles share cmd shape) or add per-profile subclasses (when they don't).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from mediastudyshelf.streaming.constants import SEGMENT_DURATION
from mediastudyshelf.streaming.session import Session


@dataclass(frozen=True)
class EncoderSpec:
    """Complete dispatch decision for one streaming session.

    cmd
        Full argv for ``subprocess.Popen`` — ready to spawn.
    output_playlist
        m3u8 path the encoder will write to. The manager waits on the first
        ``#EXTINF`` here and reads it to compute ``encoded_up_to``.
    eager_encode
        If True, the manager skips the "buffer N seconds, then pause" phase
        and skips heartbeat-driven pause/resume — the encoder runs to
        completion.
    """

    cmd: tuple[str, ...]
    output_playlist: Path
    eager_encode: bool = False


# ── Encoders ───────────────────────────────────────────────────────────────


class EncoderBase(ABC):
    """Base ffmpeg encoder. Subclasses provide codec-specific args.

    The cmd is assembled as ``[input_args] + [codec_args] + [hls_output_args]``.
    Most subclasses only need to override ``_codec_args``; override
    ``output_playlist`` or set ``eager_encode = True`` when the mode demands it.
    """

    eager_encode: bool = False

    def __init__(self, session: Session):
        self.session = session

    @property
    def output_playlist(self) -> Path:
        return self.session.internal_playlist_path

    def build_spec(self, start_time: float) -> EncoderSpec:
        cmd = (
            *self._input_args(start_time),
            *self._codec_args(),
            *self._hls_output_args(),
        )
        return EncoderSpec(
            cmd=cmd,
            output_playlist=self.output_playlist,
            eager_encode=self.eager_encode,
        )

    @abstractmethod
    def _codec_args(self) -> tuple[str, ...]:
        """Codec-specific flags between input and HLS output sections."""

    def _input_args(self, start_time: float) -> tuple[str, ...]:
        aligned_start = (start_time // SEGMENT_DURATION) * SEGMENT_DURATION
        segment_index = int(aligned_start // SEGMENT_DURATION)

        args: list[str] = ["ffmpeg", "-y"]
        if start_time > 0:
            args += ["-ss", str(aligned_start)]
        args += [
            "-fflags", "+genpts",
            "-readrate", "5",
            "-i", str(self.session.media_path),
            "-output_ts_offset", str(aligned_start),
            "-start_number", str(segment_index),
        ]
        return tuple(args)

    def _hls_output_args(self) -> tuple[str, ...]:
        return (
            "-hls_time", str(SEGMENT_DURATION),
            "-hls_list_size", "0",
            "-hls_segment_filename", str(self.session.hls_dir / "segments" / "seg_%04d.ts"),
            "-f", "hls",
            str(self.output_playlist),
        )


class EncoderTransmux(EncoderBase):
    """Copy elementary streams as-is — no re-encode (HLS-compatible source)."""

    @property
    def output_playlist(self) -> Path:
        return self.session.playlist_path

    def _codec_args(self) -> tuple[str, ...]:
        return ("-c", "copy")


class EncoderAudio(EncoderBase):
    """Audio-only re-encode to AAC 128k stereo, encoded eagerly to completion."""

    eager_encode = True

    def _codec_args(self) -> tuple[str, ...]:
        return (
            "-vn",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ac", "2",
        )


class EncoderVideo(EncoderBase):
    """Video re-encode to H.264/AAC with deterministic segment alignment."""

    def _codec_args(self) -> tuple[str, ...]:
        gop = int(self.session.fps * SEGMENT_DURATION)
        return (
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",

            # Deterministic segmentation
            "-g", str(gop),
            "-keyint_min", str(gop),
            "-sc_threshold", "0",
            # Align keyframes exactly to segment boundaries
            "-force_key_frames", f"expr:gte(t,n_forced*{SEGMENT_DURATION})",

            "-c:a", "aac",
            "-b:a", "128k",
            "-ac", "2",
        )


# ── Dispatch ───────────────────────────────────────────────────────────────


def encoder_for(session: Session) -> EncoderBase:
    """Pick the encoder for this session's media mode."""
    if session.use_copy:
        return EncoderTransmux(session)
    if session.is_audio_only:
        return EncoderAudio(session)
    return EncoderVideo(session)
