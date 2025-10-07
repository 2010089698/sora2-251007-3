"""FastAPI application implementing the Sora2 video MVP backend."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .database import VideoJob, VideoStatusEnum, create_engine_and_session, init_db, session_scope
from .openai_client import OpenAIVideosClient
from .schemas import CreateVideoRequest, build_job_schema, generate_uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sora2.db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_VIDEO_MODEL", "sora-1.0")
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
            if status == VideoStatusEnum.COMPLETED.value:
                logger.info("Job %s completed", job.id)
                job.error_message = None
                _update_content_metadata(job, response)
            elif status == VideoStatusEnum.FAILED.value:
                job.error_message = response.get("error", {}).get("message") or "Generation failed"
            else:
                job.error_message = None
            session.add(job)


def _update_content_metadata(job: VideoJob, response: dict) -> None:
    payload = response.get("result") or response
    variants = payload.get("content_variants") or payload.get("variants") or []
    variant = (
        payload.get("default_variant")
        or payload.get("variant")
        or (variants[0] if isinstance(variants, list) and variants else None)
    )
    if variant:
        job.content_variant = variant
    elif job.content_variant is None:
        job.content_variant = "source"

    token = payload.get("content_token") or payload.get("download_token")
    if token:
        job.content_token = token

    expires_at = payload.get("content_token_expires_at") or payload.get("token_expires_at")
    parsed_expires = _parse_datetime(expires_at)
    if parsed_expires:
        job.content_token_expires_at = parsed_expires

    if job.content_ready_at is None:
        job.content_ready_at = datetime.utcnow()


@app.post("/api/videos")
async def create_video(
    request: CreateVideoRequest,
    db: Session = Depends(get_db),
    client: OpenAIVideosClient = Depends(get_openai_client),
):
    payload = {"prompt": request.prompt}
    if request.duration is not None:
        payload["duration"] = request.duration
    if request.format is not None:
        payload["format"] = request.format
    size = aspect_ratio_to_resolution(request.aspect_ratio)
    if size is not None:
        payload["size"] = size
    try:
        response = await client.create_video(payload)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    job_id = generate_uuid()
    payload = response.get("result") or response
    token = payload.get("content_token") or payload.get("download_token")
    expires_at = _parse_datetime(payload.get("content_token_expires_at") or payload.get("token_expires_at"))

    job = VideoJob(
        id=job_id,
        user_id=request.user_id or "demo-user",
        prompt=request.prompt,
        sora_job_id=response["id"],
        status=response.get("status", VideoStatusEnum.QUEUED.value),
        aspect_ratio=request.aspect_ratio,
        duration=request.duration,
        format=request.format,
        content_variant=(response.get("result") or response).get("default_variant")
        if response.get("status") == VideoStatusEnum.COMPLETED.value
        else None,
        content_ready_at=datetime.utcnow()
        if response.get("status") == VideoStatusEnum.COMPLETED.value
        else None,
        content_token=token,
        content_token_expires_at=expires_at,
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
async def get_video_media(
    job_id: str,
    variant: Optional[str] = Query(None, description="OpenAI content variant"),
    db: Session = Depends(get_db),
    client: OpenAIVideosClient = Depends(get_openai_client),
):
    job: Optional[VideoJob] = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != VideoStatusEnum.COMPLETED.value:
        raise HTTPException(status_code=409, detail="Video is not ready")

    chosen_variant = variant or job.content_variant or "source"
    stream_ctx = client.stream_video_content(job.sora_job_id, chosen_variant, job.content_token)
    try:
        remote_response = await stream_ctx.__aenter__()
    except httpx.HTTPStatusError as exc:
        await stream_ctx.__aexit__(type(exc), exc, exc.__traceback__)
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except httpx.RequestError as exc:
        await stream_ctx.__aexit__(type(exc), exc, exc.__traceback__)
        raise HTTPException(status_code=502, detail=str(exc))

    media_type = remote_response.headers.get("content-type") or "video/mp4"
    content_length = remote_response.headers.get("content-length")

    async def iterator():
        try:
            async for chunk in remote_response.aiter_bytes():
                yield chunk
        finally:
            await stream_ctx.__aexit__(None, None, None)

    streaming_response = StreamingResponse(iterator(), media_type=media_type)
    if content_length:
        streaming_response.headers["Content-Length"] = content_length
    return streaming_response


@app.get("/api/videos/{job_id}/stream")
async def deprecated_stream_endpoint(job_id: str):
    raise HTTPException(
        status_code=410,
        detail=f"This endpoint has moved to /api/videos/{job_id}/media",
    )


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


def aspect_ratio_to_resolution(aspect_ratio: Optional[str]) -> Optional[str]:
    if aspect_ratio is None:
        return None
    presets = {
        "16:9": "1920x1080",
        "9:16": "1080x1920",
        "1:1": "1024x1024",
        "4:3": "1440x1080",
    }
    return presets.get(aspect_ratio, aspect_ratio)


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None
