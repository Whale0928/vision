from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from analysis import analyze_image
from app.api.routes import create_api_router
from app.services.analyzer import Analyzer

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
TEMPLATE_DIR = APP_DIR / "templates"


def create_app(analyzer: Analyzer = analyze_image) -> FastAPI:
    app = FastAPI(title="Whisky Vision Pilot")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(create_api_router(analyzer))

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(TEMPLATE_DIR / "index.html", media_type="text/html")

    return app


app = create_app()
