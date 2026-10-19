import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import is_production
from backend.storage.sql_models import Base


LOCAL_DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "postbridge.local.db"


def database_url() -> str:
    configured = os.getenv("POSTBRIDGE_DATABASE_URL", "").strip()
    if configured:
        return configured
    if is_production():
        raise RuntimeError("PostBridge database configuration is required.")
    return f"sqlite:///{LOCAL_DATABASE_PATH.as_posix()}"


@lru_cache(maxsize=4)
def engine_for_url(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    if url.startswith("sqlite"):
        LOCAL_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(engine)
    return engine


@lru_cache(maxsize=4)
def session_factory_for_url(url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=engine_for_url(url), expire_on_commit=False)


def session_factory() -> sessionmaker[Session]:
    return session_factory_for_url(database_url())
