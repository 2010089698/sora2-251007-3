"""Pydantic schemas for API requests and responses."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, validator

from .database import VideoJob


class CreateVideoRequest(BaseModel):
    prompt: str = Field(..., min_length=4, description="Natural language prompt for the video.")
    aspect_ratio: Optional[str] = Field(
        default="16:9", description="Aspect ratio shorthand (e.g. 16:9, 9:16, 1:1)."
    )
    duration: Optional[int] = Field(
        default=8, ge=1, le=60, description="Desired duration of the generated clip in seconds."
    )
    format: Optional[str] = Field(default="mp4", description="Requested file format.")
    user_id: Optional[str] = Field(default="demo-user", description="Identifier for the authenticated user.")

    @validator("prompt")
    def prompt_must_have_words(cls, value: str) -> str:
        if len(value.split()) < 2:
            raise ValueError("Prompt must contain at least two words for better results.")
        return value


class VideoJobSchema(BaseModel):
    id: str
    prompt: str
    sora_job_id: str
    status: str
    error_message: Optional[str]
    aspect_ratio: Optional[str]
    duration: Optional[int]
    format: Optional[str]
    created_at: datetime
    updated_at: datetime
    content_variant: Optional[str]
    content_ready_at: Optional[datetime]

    class Config:
        orm_mode = True


def generate_uuid() -> str:
    return str(uuid4())


def build_job_schema(job: VideoJob) -> VideoJobSchema:
    return VideoJobSchema.from_orm(job)
