import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.auth_api import router as auth_router
from backend.caption_api import router as caption_router
from backend.config import csv_environment, is_production, validate_runtime_environment
from backend.draft_api import media_router
from backend.draft_api import router as draft_router
from backend.instagram_api import router as instagram_router
from backend.tiktok_api import router as tiktok_router

logging.basicConfig(level=logging.INFO)
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
validate_runtime_environment()

app = FastAPI(title="PostBridge API")
for router in (auth_router, instagram_router, tiktok_router, draft_router, media_router, caption_router):
    app.include_router(router)

DEFAULT_CORS_ORIGINS = "https://postbridge.dev,http://localhost:3000"

app.add_middleware(
    CORSMiddleware,
    allow_origins=csv_environment("POSTBRIDGE_CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
if is_production():
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=csv_environment("POSTBRIDGE_ALLOWED_HOSTS"))


@app.get("/")
def root() -> dict:
    return {"name": "PostBridge API", "status": "running", "docs": "/docs"}


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
