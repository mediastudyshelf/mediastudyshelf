"""Pydantic shapes for the streaming control plane (/api/stream/*)."""

from pydantic import BaseModel


class StreamPrepareRequest(BaseModel):
    media_url: str  # /media/assets/... path (video or audio)
    start_time: float = 0.0  # seconds; where ffmpeg should begin encoding


class StreamPrepareResponse(BaseModel):
    url: str
    id: str


class StreamHeartbeatRequest(BaseModel):
    time: float  # playhead position in seconds
