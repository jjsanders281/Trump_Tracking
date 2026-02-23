from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

def normalize_database_url(raw_url: str) -> str:
    """
    Normalize incoming database URLs so SQLAlchemy uses a supported driver.

    Neon often provides `postgresql://...`; for psycopg3 we prefer
    `postgresql+psycopg://...`.
    """
    if raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql://", 1)
    if raw_url.startswith("postgresql://") and "+psycopg" not in raw_url:
        raw_url = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw_url


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///./tracker.db"))

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine_kwargs = {"connect_args": connect_args}
if DATABASE_URL.startswith("postgresql+psycopg://"):
    # Neon/managed DB connections can drop; keep pool healthy.
    engine_kwargs.update({"pool_pre_ping": True, "pool_recycle": 1800})

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
