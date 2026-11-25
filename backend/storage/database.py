"""SQLAlchemy database configuration; SQLite URLs are reserved for tests."""

import os
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import is_production
from backend.storage.sql_models import Base

DEFAULT_DATABASE_URL = "postgresql+psycopg://creatormind:creatormind@db:5432/creatormind"


def database_url() -> str:
    configured = os.getenv("POSTBRIDGE_DATABASE_URL", "").strip()
    if configured:
        return configured
    if is_production():
        raise RuntimeError("PostBridge database configuration is required.")
    return DEFAULT_DATABASE_URL


@lru_cache(maxsize=4)
def engine_for_url(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    if url.startswith("sqlite"):
        Base.metadata.create_all(engine)
    return engine


@lru_cache(maxsize=4)
def session_factory_for_url(url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=engine_for_url(url), expire_on_commit=False)


def session_factory() -> sessionmaker[Session]:
    return session_factory_for_url(database_url())
