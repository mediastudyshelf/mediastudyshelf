"""Tunable parameters for the HLS streaming pipeline.

Kept in one place so operators can audit (and override at fork-time) every
buffer/timeout/segment knob without hunting through the implementation files.
"""

ENCODE_CHUNK = 60         # seconds of content per ffmpeg run
BUFFER_THRESHOLD = 30     # respawn when playhead is within this many seconds of end
HEARTBEAT_TIMEOUT = 60    # seconds without heartbeat before cleanup
SESSION_GC_INTERVAL = 15  # seconds between session GC passes
SEGMENT_DURATION = 10     # HLS segment length in seconds
FPS_DEFAULT = 24          # fallback when ffprobe cannot determine frame rate
