from __future__ import annotations

import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from app.db.models import FileRecord
from app.db.session import create_database
from app.images.preprocess import (
    ImagePreprocessError,
    PreprocessStep,
    calculate_sha256,
    preprocess_image_bytes,
)
from app.repositories.files import FileRepository
from app.schemas import (
    FileCreateResponse,
    FileDetailResponse,
    FileListItem,
    FileListResponse,
    FileStep,
    ProcessedImageMeta,
    SourceImageMeta,
)
from app.storage.object_store import ObjectStore

SUPPORTED_ORIGINAL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
DEFAULT_DATA_DIR = Path(os.getenv("VISION_DATA_DIR", ".data"))


@dataclass(frozen=True)
class StoredImage:
    path: Path
    media_type: str


class FileIngestionService:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.object_store = ObjectStore(data_dir / "objects")
        self.repository = FileRepository(create_database(data_dir / "vision.db"))

    def store_upload(self, payload: bytes, original_filename: str | None) -> FileCreateResponse:
        started_at = time.perf_counter()
        original_sha256 = calculate_sha256(payload)
        hash_step = FileStep(label="원본 해시 계산", elapsed_ms=elapsed_ms(started_at))

        started_at = time.perf_counter()
        existing = self.repository.find_by_original_sha256(original_sha256)
        if existing is not None:
            duplicate_step = FileStep(label="중복 이미지 확인", elapsed_ms=elapsed_ms(started_at))
            return self._create_response(existing, duplicate=True, steps=[hash_step, duplicate_step])

        file_id = make_file_id()
        now = utc_now()
        original_path = make_object_path("original", now, file_id, original_extension(original_filename))
        processed_path = make_object_path("processed", now, file_id, ".jpg")
        thumbnail_path = make_object_path("thumbnails", now, file_id, ".jpg")

        started_at = time.perf_counter()
        self.object_store.write_bytes(original_path, payload)
        original_step = FileStep(label="원본 저장", elapsed_ms=elapsed_ms(started_at))

        started_at = time.perf_counter()
        try:
            result = preprocess_image_bytes(payload, filename=original_filename)
        except ImagePreprocessError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        preprocess_step = convert_preprocess_step(result.steps[0], elapsed_ms(started_at))

        started_at = time.perf_counter()
        self.object_store.write_bytes(processed_path, result.processed_bytes)
        self.object_store.write_bytes(thumbnail_path, result.thumbnail_bytes)
        processed_step = FileStep(label="보정 이미지 저장", elapsed_ms=elapsed_ms(started_at))

        started_at = time.perf_counter()
        record = FileRecord(
            id=file_id,
            created_at=now.isoformat(),
            original_filename=safe_filename(original_filename),
            status="processed_saved",
            source_mime=result.source_mime,
            source_size_bytes=result.source_size_bytes,
            source_width=result.source_size[0],
            source_height=result.source_size[1],
            original_object_path=original_path,
            original_sha256=result.original_sha256,
            processed_object_path=processed_path,
            processed_sha256=result.processed_sha256,
            processed_mime=result.processed_mime,
            processed_size_bytes=result.processed_size_bytes,
            processed_width=result.processed_size[0],
            processed_height=result.processed_size[1],
            thumbnail_object_path=thumbnail_path,
            thumbnail_size_bytes=result.thumbnail_size_bytes,
            preprocess_profile=result.preprocess_profile,
            original_saved_at=now.isoformat(),
            processed_saved_at=utc_now().isoformat(),
        )
        record = self.repository.insert(record)
        db_step = FileStep(label="DB files 갱신", elapsed_ms=elapsed_ms(started_at))

        return self._create_response(
            record,
            duplicate=False,
            steps=[hash_step, original_step, preprocess_step, processed_step, db_step],
        )

    def list_files(self, limit: int = 40) -> FileListResponse:
        records = self.repository.list_recent(limit=limit)
        return FileListResponse(items=[to_list_item(record) for record in records], next_cursor=None)

    def get_detail(self, file_id: str) -> FileDetailResponse:
        record = self._get_record(file_id)
        return to_detail(record)

    def get_image(self, file_id: str, kind: str) -> StoredImage:
        record = self._get_record(file_id)
        if kind == "original":
            object_path = record.original_object_path
            media_type = record.source_mime
        elif kind == "processed":
            object_path = record.processed_object_path
            media_type = record.processed_mime
        elif kind == "thumbnail":
            object_path = record.thumbnail_object_path
            media_type = "image/jpeg"
        else:
            raise HTTPException(status_code=404, detail="이미지 종류를 찾을 수 없습니다")

        if not self.object_store.exists(object_path):
            raise HTTPException(status_code=410, detail="저장된 이미지 파일을 찾을 수 없습니다")
        return StoredImage(path=self.object_store.system_path(object_path), media_type=media_type)

    def _get_record(self, file_id: str) -> FileRecord:
        record = self.repository.find_by_id(file_id)
        if record is None:
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")
        return record

    def _create_response(
        self,
        record: FileRecord,
        *,
        duplicate: bool,
        steps: list[FileStep],
    ) -> FileCreateResponse:
        return FileCreateResponse(
            file_id=record.id,
            status=record.status,
            duplicate=duplicate,
            original_sha256=record.original_sha256,
            processed_sha256=record.processed_sha256,
            original_url=file_url(record.id, "original"),
            processed_url=file_url(record.id, "processed"),
            thumbnail_url=file_url(record.id, "thumbnail"),
            steps=steps,
        )


def create_file_service(data_dir: Path | None = None) -> FileIngestionService:
    return FileIngestionService(data_dir or DEFAULT_DATA_DIR)


def elapsed_ms(started_at: float) -> int:
    return round((time.perf_counter() - started_at) * 1000)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_file_id() -> str:
    return f"file_{uuid.uuid4().hex[:16]}"


def make_object_path(kind: str, created_at: datetime, file_id: str, extension: str) -> str:
    return f"files/{kind}/{created_at:%Y/%m/%d}/{file_id}{extension}"


def original_extension(filename: str | None) -> str:
    if not filename:
        return ".bin"
    suffix = Path(filename).suffix.lower()
    return suffix if suffix in SUPPORTED_ORIGINAL_EXTENSIONS else ".bin"


def safe_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    name = Path(filename).name
    return re.sub(r"[^A-Za-z0-9가-힣._ -]", "_", name)


def convert_preprocess_step(step: PreprocessStep, elapsed: int) -> FileStep:
    return FileStep(
        label=step.label,
        elapsed_ms=elapsed,
        children=[
            FileStep(label=child.label, elapsed_ms=child.elapsed_ms)
            for child in step.children
        ],
    )


def file_url(file_id: str, kind: str) -> str:
    return f"/api/files/{file_id}/{kind}"


def to_list_item(record: FileRecord) -> FileListItem:
    return FileListItem(
        file_id=record.id,
        created_at=record.created_at,
        original_filename=record.original_filename,
        status=record.status,
        thumbnail_url=file_url(record.id, "thumbnail"),
        processed_width=record.processed_width,
        processed_height=record.processed_height,
        original_sha256_short=record.original_sha256[:8],
    )


def to_detail(record: FileRecord) -> FileDetailResponse:
    return FileDetailResponse(
        file_id=record.id,
        created_at=record.created_at,
        status=record.status,
        original_filename=record.original_filename,
        original_sha256=record.original_sha256,
        processed_sha256=record.processed_sha256,
        original_url=file_url(record.id, "original"),
        processed_url=file_url(record.id, "processed"),
        thumbnail_url=file_url(record.id, "thumbnail"),
        source=SourceImageMeta(
            mime=record.source_mime,
            size_bytes=record.source_size_bytes,
            width=record.source_width,
            height=record.source_height,
        ),
        processed=ProcessedImageMeta(
            mime=record.processed_mime,
            size_bytes=record.processed_size_bytes,
            width=record.processed_width,
            height=record.processed_height,
            profile=record.preprocess_profile,
        ),
    )
