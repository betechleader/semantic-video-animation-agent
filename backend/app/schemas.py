from pydantic import BaseModel, ConfigDict, Field


class VideoMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_seconds: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    frame_rate: float = Field(gt=0)
    video_codec: str
    audio_codec: str | None = None
    has_video: bool
    has_audio: bool
