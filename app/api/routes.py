from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.schemas import AnalyzeResponse, FileCreateResponse, FileDetailResponse, FileListResponse
from app.services.analyzer import AnalysisTimeoutError, Analyzer, analyze_upload, stream_analyze_upload
from app.services.file_ingestion import FileIngestionService


def create_api_router(
    analyzer: Analyzer,
    file_service_provider: Callable[[], FileIngestionService],
) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.post("/analyze", response_model=AnalyzeResponse)
    async def analyze(
        image: UploadFile = File(),
        model: str = Form(default="gpt-4o-mini"),
    ) -> AnalyzeResponse:
        try:
            return await analyze_upload(
                image=image,
                model=model,
                analyzer=analyzer,
                file_service=file_service_provider(),
            )
        except AnalysisTimeoutError as exc:
            raise HTTPException(status_code=504, detail=str(exc)) from exc

    @router.post("/analyze/stream")
    async def analyze_stream(
        image: UploadFile = File(),
        model: str = Form(default="gpt-4o-mini"),
    ) -> StreamingResponse:
        return StreamingResponse(
            stream_analyze_upload(
                image=image,
                model=model,
                analyzer=analyzer,
                file_service=file_service_provider(),
            ),
            media_type="application/x-ndjson",
        )

    @router.post("/files", response_model=FileCreateResponse)
    async def create_file(image: UploadFile = File()) -> FileCreateResponse:
        payload = await image.read()
        await image.close()
        return file_service_provider().store_upload(payload, image.filename)

    @router.get("/files", response_model=FileListResponse)
    async def list_files(limit: int = Query(default=40, ge=1, le=100)) -> FileListResponse:
        return file_service_provider().list_files(limit=limit)

    @router.get("/files/{file_id}", response_model=FileDetailResponse)
    async def get_file(file_id: str) -> FileDetailResponse:
        return file_service_provider().get_detail(file_id)

    @router.get("/files/{file_id}/{kind}", response_class=FileResponse)
    async def get_file_image(file_id: str, kind: str) -> FileResponse:
        stored = file_service_provider().get_image(file_id, kind)
        return FileResponse(
            stored.path,
            media_type=stored.media_type,
            headers={"Cache-Control": "private, max-age=3600"},
        )

    return router
