"""ffprobe-based media inspection for the streaming pipeline.

``probe_media`` returns the codec/duration/fps tuple, and ``_can_copy``
turns that into the transmux-vs-re-encode decision.
"""

import json
import logging
import subprocess
from pathlib import Path

from mediastudyshelf.streaming.constants import FPS_DEFAULT

logger = logging.getLogger(__name__)


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


def can_copy(video_codec: str | None, audio_codec: str | None) -> bool:
    """Return True if source codecs are HLS-compatible (no re-encode needed)."""
    return video_codec == "h264" and audio_codec in ("aac", None)
