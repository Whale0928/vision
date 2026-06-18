from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.schemas import AnalyzeResponse
from app.services.analyzer import Analyzer, analyze_upload


def create_api_router(analyzer: Analyzer) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.post("/analyze", response_model=AnalyzeResponse)
    async def analyze(
        image: UploadFile = File(),
        model: str = Form(default="gpt-4o-mini"),
    ) -> AnalyzeResponse:
        return await analyze_upload(image=image, model=model, analyzer=analyzer)

    return router
