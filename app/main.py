from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from analysis import analyze_image
from app.api.routes import create_api_router
from app.services.analyzer import Analyzer
from app.services.file_ingestion import FileIngestionService, create_file_service

ROOT_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
TEMPLATE_DIR = APP_DIR / "templates"


def create_app(
    analyzer: Analyzer = analyze_image,
    *,
    data_dir: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Whisky Vision Pilot")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    file_service: FileIngestionService | None = None

    def get_file_service() -> FileIngestionService:
        nonlocal file_service
        if file_service is None:
            resolved_data_dir = data_dir or Path(os.getenv("VISION_DATA_DIR", ".data"))
            file_service = create_file_service(resolved_data_dir)
        return file_service

    app.include_router(create_api_router(analyzer, get_file_service))

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(TEMPLATE_DIR / "index.html", media_type="text/html")

    @app.get("/image-preprocess", include_in_schema=False)
    async def image_preprocess_sample() -> FileResponse:
        return FileResponse(ROOT_DIR / "image-preprocess.html", media_type="text/html")

    return app


app = create_app()
