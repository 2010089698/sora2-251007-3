"""Database utilities for the Sora2 video MVP backend."""
from __future__ import annotations

import contextlib
from datetime import datetime
from enum import Enum
from typing import Iterator

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import text

# Naming convention for constraints for reliable migrations/backups
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=convention)
Base = declarative_base(metadata=metadata)


class VideoStatusEnum(str, Enum):
    """Enumeration of job statuses tracked in the database."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoJob(Base):
    __tablename__ = "video_jobs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(255), nullable=False)
    prompt = Column(Text, nullable=False)
    sora_job_id = Column(String(255), nullable=False, unique=True)
    status = Column(String(32), nullable=False, default=VideoStatusEnum.QUEUED.value)
    error_message = Column(Text, nullable=True)
    aspect_ratio = Column(String(16), nullable=True)
    duration = Column(Integer, nullable=True)
    format = Column(String(16), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    content_variant = Column(String(64), nullable=True)
    content_token = Column(Text, nullable=True)
    content_token_expires_at = Column(DateTime, nullable=True)
    content_ready_at = Column(DateTime, nullable=True)


def create_engine_and_session(database_url: str):
    """Create the SQLAlchemy engine and session factory."""

    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, SessionLocal


def init_db(engine) -> None:
    """Create database tables if they do not already exist."""

    Base.metadata.create_all(bind=engine)
    ensure_content_columns(engine)


def ensure_content_columns(engine) -> None:
    """Ensure newer content-related columns exist for legacy databases."""

    if engine.dialect.name != "sqlite":
        return
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(video_jobs)"))
        existing_columns = {row[1] for row in result}
        alterations = []
        if "content_variant" not in existing_columns:
            alterations.append("ALTER TABLE video_jobs ADD COLUMN content_variant TEXT")
        if "content_token" not in existing_columns:
            alterations.append("ALTER TABLE video_jobs ADD COLUMN content_token TEXT")
        if "content_token_expires_at" not in existing_columns:
            alterations.append("ALTER TABLE video_jobs ADD COLUMN content_token_expires_at TEXT")
        if "content_ready_at" not in existing_columns:
            alterations.append("ALTER TABLE video_jobs ADD COLUMN content_ready_at TEXT")
        for statement in alterations:
            conn.execute(text(statement))


@contextlib.contextmanager
def session_scope(SessionLocal) -> Iterator:
    """Provide a transactional scope around a series of operations."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
