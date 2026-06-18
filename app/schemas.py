from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DebugStep(BaseModel):
    label: str
    elapsed_ms: int = Field(ge=0)


class AnalyzeResponse(BaseModel):
    model: str
    result: dict[str, Any]
    debug_steps: list[DebugStep]
    total_ms: int = Field(ge=0)


class FileStep(BaseModel):
    label: str
    elapsed_ms: int = Field(ge=0)
    children: list["FileStep"] = Field(default_factory=list)


class FileCreateResponse(BaseModel):
    file_id: str
    status: str
    duplicate: bool
    original_sha256: str
    processed_sha256: str
    original_url: str
    processed_url: str
    thumbnail_url: str
    steps: list[FileStep]


class FileListItem(BaseModel):
    file_id: str
    created_at: str
    original_filename: str | None
    status: str
    thumbnail_url: str
    processed_width: int
    processed_height: int
    original_sha256_short: str


class FileListResponse(BaseModel):
    items: list[FileListItem]
    next_cursor: str | None = None


class SourceImageMeta(BaseModel):
    mime: str
    size_bytes: int
    width: int
    height: int


class ProcessedImageMeta(BaseModel):
    mime: str
    size_bytes: int
    width: int
    height: int
    profile: str


class FileDetailResponse(BaseModel):
    file_id: str
    created_at: str
    status: str
    original_filename: str | None
    original_sha256: str
    processed_sha256: str
    original_url: str
    processed_url: str
    thumbnail_url: str
    source: SourceImageMeta
    processed: ProcessedImageMeta
