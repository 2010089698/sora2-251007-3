"""FastAPI application implementing the Sora2 video MVP backend."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .database import (
    VideoAsset,
    VideoJob,
    VideoStatusEnum,
    create_engine_and_session,
    init_db,
    session_scope,
)
from .openai_client import OpenAIVideosClient
from .schemas import CreateVideoRequest, build_job_schema, generate_uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sora2.db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_VIDEO_MODEL", "sora-2")
OPENAI_BETA_HEADER = os.getenv("OPENAI_VIDEO_BETA_HEADER", "video-generation=2")
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "10"))

engine, SessionLocal = create_engine_and_session(DATABASE_URL)
init_db(engine)

app = FastAPI(title="Sora2 Video Generation MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_openai_client() -> OpenAIVideosClient:
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")
    return OpenAIVideosClient(
        api_key=OPENAI_API_KEY,
        api_base=OPENAI_API_BASE,
        model=OPENAI_MODEL,
        beta_header=OPENAI_BETA_HEADER,
    )


def get_db():
    with session_scope(SessionLocal) as session:
        yield session


@app.on_event("startup")
async def startup_event() -> None:
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY is not set. API calls will fail until configured.")
    asyncio.create_task(poll_pending_jobs())


async def poll_pending_jobs() -> None:
    """Background task that polls OpenAI for job updates."""

    await asyncio.sleep(1)  # give server time to start
    client: Optional[OpenAIVideosClient] = None
    try:
        client = await get_openai_client()
    except HTTPException:
        logger.warning("OpenAI client unavailable during startup; polling paused until configured.")

    while True:
        try:
            if client is None:
                client = await get_openai_client()
            await _poll_once(client)
        except HTTPException:
            logger.error("OpenAI client misconfigured; retrying after backoff")
            client = None
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error while polling jobs: %s", exc)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _poll_once(client: OpenAIVideosClient) -> None:
    with session_scope(SessionLocal) as session:
        jobs: List[VideoJob] = (
            session.query(VideoJob)
            .filter(VideoJob.status.in_([VideoStatusEnum.QUEUED.value, VideoStatusEnum.PROCESSING.value]))
            .all()
        )
        for job in jobs:
            try:
                logger.info("Polling job %s (status=%s)", job.id, job.status)
                response = await client.retrieve_video(job.sora_job_id)
            except httpx.HTTPStatusError as exc:
                logger.warning("OpenAI returned error for job %s: %s", job.id, exc.response.text)
                job.error_message = exc.response.text
                job.status = VideoStatusEnum.FAILED.value
                job.updated_at = datetime.utcnow()
                session.add(job)
                continue
            except httpx.RequestError as exc:
                logger.warning("Network error while polling job %s: %s", job.id, exc)
                continue

            status = response.get("status", job.status)
            job.status = status
            job.updated_at = datetime.utcnow()
            job.seconds = response.get("seconds") or job.seconds
            job.size = response.get("size") or job.size
            if status == VideoStatusEnum.COMPLETED.value:
                logger.info("Job %s completed", job.id)
                job.error_message = None
                _sync_assets(job, response)
            elif status == VideoStatusEnum.FAILED.value:
                job.error_message = response.get("error", {}).get("message") or "Generation failed"
            else:
                job.error_message = None
            session.add(job)


def _sync_assets(job: VideoJob, response: dict) -> None:
    existing_asset = job.assets[0] if job.assets else None
    assets = response.get("result", {}).get("assets") or response.get("assets") or []
    if not assets:
        return
    asset_payload = assets[0]
    if existing_asset is None:
        existing_asset = VideoAsset(id=generate_uuid(), job_id=job.id)
        job.assets.append(existing_asset)
    existing_asset.download_url = asset_payload.get("download_url")
    existing_asset.preview_url = asset_payload.get("stream_url") or asset_payload.get("preview_url")
    existing_asset.thumbnail_url = asset_payload.get("thumbnail_url")
    existing_asset.duration_seconds = asset_payload.get("duration")
    existing_asset.resolution = asset_payload.get("resolution")
    file_size = asset_payload.get("file_size")
    existing_asset.file_size = int(file_size) if file_size is not None else None


@app.post("/api/videos")
async def create_video(
    request: CreateVideoRequest,
    db: Session = Depends(get_db),
    client: OpenAIVideosClient = Depends(get_openai_client),
):
    payload = {
        "prompt": request.prompt,
        "seconds": int(request.seconds.value),
    }
    normalized_size = aspect_ratio_to_resolution(request.size.value)
    size_value = normalized_size or request.size.value
    payload["size"] = size_value
    try:
        response = await client.create_video(payload)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    job_id = generate_uuid()
    job = VideoJob(
        id=job_id,
        user_id=request.user_id or "demo-user",
        prompt=request.prompt,
        sora_job_id=response["id"],
        status=response.get("status", VideoStatusEnum.QUEUED.value),
        seconds=int(request.seconds.value),
        size=size_value,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"job": build_job_schema(job)}


@app.get("/api/videos")
async def list_videos(db: Session = Depends(get_db)):
    jobs: List[VideoJob] = db.query(VideoJob).order_by(VideoJob.created_at.desc()).all()
    return {"jobs": [build_job_schema(job) for job in jobs]}


@app.get("/api/videos/{job_id}")
async def get_video(job_id: str, db: Session = Depends(get_db)):
    job: Optional[VideoJob] = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": build_job_schema(job)}


@app.get("/api/videos/{job_id}/media")
async def get_video_media(job_id: str, db: Session = Depends(get_db)):
    job: Optional[VideoJob] = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.assets:
        raise HTTPException(status_code=404, detail="No assets available for this job yet")
    asset = job.assets[0]
    return {
        "asset": {
            "download_url": asset.download_url,
            "preview_url": asset.preview_url,
            "thumbnail_url": asset.thumbnail_url,
            "duration_seconds": asset.duration_seconds,
            "resolution": asset.resolution,
            "file_size": asset.file_size,
        }
    }


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


OFFICIAL_SIZES = {
    "480x480",
    "720x1280",
    "1080x1920",
    "1920x1080",
    "2560x1440",
}


def aspect_ratio_to_resolution(preference: Optional[str]) -> Optional[str]:
    if preference is None:
        return None
    value = preference.strip()
    if value in OFFICIAL_SIZES:
        return value
    presets = {
        "1:1": "480x480",
        "square": "480x480",
        "9:16": "1080x1920",
        "portrait": "1080x1920",
        "vertical": "1080x1920",
        "16:9": "1920x1080",
        "landscape": "1920x1080",
        "4:3": "1920x1080",
    }
    resolved = presets.get(value)
    if resolved in OFFICIAL_SIZES:
        return resolved
    return None
