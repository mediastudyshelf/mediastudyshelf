"""m3u8 playlist parsing and synthesis."""

import math
from pathlib import Path

from mediastudyshelf.streaming.constants import SEGMENT_DURATION


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
