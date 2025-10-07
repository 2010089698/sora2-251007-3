"""Database utilities for the Sora2 video MVP backend."""
from __future__ import annotations

import contextlib
from datetime import datetime
from enum import Enum
from typing import Iterator

from sqlalchemy import Column, DateTime, ForeignKey, Integer, MetaData, String, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

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
    seconds = Column(Integer, nullable=True)
    size = Column(String(16), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    assets = relationship("VideoAsset", back_populates="job", cascade="all, delete-orphan")


class VideoAsset(Base):
    __tablename__ = "video_assets"

    id = Column(String(36), primary_key=True)
    job_id = Column(String(36), ForeignKey("video_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    download_url = Column(Text, nullable=True)
    preview_url = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    resolution = Column(String(32), nullable=True)
    file_size = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    job = relationship("VideoJob", back_populates="assets")


def create_engine_and_session(database_url: str):
    """Create the SQLAlchemy engine and session factory."""

    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, SessionLocal


def init_db(engine) -> None:
    """Create database tables if they do not already exist."""

    Base.metadata.create_all(bind=engine)


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
