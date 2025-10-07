"""Pydantic schemas for API requests and responses."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, validator

from .database import VideoAsset, VideoJob


class SecondsEnum(int, Enum):
    FOUR = 4
    EIGHT = 8
    TWELVE = 12


class SizeEnum(str, Enum):
    SQUARE_480 = "480x480"
    PORTRAIT_720 = "720x1280"
    PORTRAIT_1080 = "1080x1920"
    LANDSCAPE_1080 = "1920x1080"
    LANDSCAPE_1440 = "2560x1440"


class CreateVideoRequest(BaseModel):
    prompt: str = Field(..., min_length=4, description="Natural language prompt for the video.")
    seconds: SecondsEnum = Field(
        default=SecondsEnum.EIGHT,
        description="Clip length in seconds. Allowed values: 4, 8, 12.",
    )
    size: SizeEnum = Field(
        default=SizeEnum.LANDSCAPE_1080,
        description="Resolution preset provided by the OpenAI Videos API.",
    )
    user_id: Optional[str] = Field(default="demo-user", description="Identifier for the authenticated user.")

    @validator("prompt")
    def prompt_must_have_words(cls, value: str) -> str:
        if len(value.split()) < 2:
            raise ValueError("Prompt must contain at least two words for better results.")
        return value


class VideoAssetSchema(BaseModel):
    id: str
    download_url: Optional[str]
    preview_url: Optional[str]
    thumbnail_url: Optional[str]
    duration_seconds: Optional[int]
    resolution: Optional[str]
    file_size: Optional[int]
    created_at: datetime

    class Config:
        orm_mode = True


class VideoJobSchema(BaseModel):
    id: str
    prompt: str
    sora_job_id: str
    status: str
    error_message: Optional[str]
    seconds: Optional[int]
    size: Optional[str]
    created_at: datetime
    updated_at: datetime
    assets: List[VideoAssetSchema]

    class Config:
        orm_mode = True


def generate_uuid() -> str:
    return str(uuid4())


def build_asset_schema(asset: VideoAsset) -> VideoAssetSchema:
    return VideoAssetSchema.from_orm(asset)


def build_job_schema(job: VideoJob) -> VideoJobSchema:
    return VideoJobSchema.from_orm(job)
