from __future__ import annotations

import asyncio
import os
import json
import tempfile
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from analysis import analyze_image
from app.schemas import AnalyzeResponse, DebugStep
from app.services.file_ingestion import FileIngestionService

Analyzer = Callable[[str, str], dict[str, Any]]
DEFAULT_ANALYSIS_TIMEOUT_SECONDS = 60.0


class AnalysisTimeoutError(RuntimeError):
    pass


def elapsed_ms(started_at: float) -> int:
    return round((time.perf_counter() - started_at) * 1000)


def analysis_timeout_seconds() -> float:
    value = os.getenv("VISION_ANALYSIS_TIMEOUT_SECONDS")
    if value is None:
        return DEFAULT_ANALYSIS_TIMEOUT_SECONDS
    try:
        parsed = float(value)
    except ValueError:
        return DEFAULT_ANALYSIS_TIMEOUT_SECONDS
    return parsed if parsed > 0 else DEFAULT_ANALYSIS_TIMEOUT_SECONDS


async def run_analyzer_with_timeout(analyzer: Analyzer, image_path: str, model: str) -> dict[str, Any]:
    timeout = analysis_timeout_seconds()
    try:
        return await asyncio.wait_for(
            run_in_threadpool(analyzer, image_path, model),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        raise AnalysisTimeoutError(f"분석 시간이 초과되었습니다. 제한 시간: {timeout:g}초") from exc


def encode_stream_event(payload: dict[str, Any]) -> str:
    return f"{json.dumps(payload, ensure_ascii=False)}\n"


def step_to_dict(step: DebugStep) -> dict[str, Any]:
    return step.model_dump() if hasattr(step, "model_dump") else step.dict()


def response_to_dict(response: AnalyzeResponse) -> dict[str, Any]:
    return response.model_dump() if hasattr(response, "model_dump") else response.dict()


async def analyze_upload(
    image: UploadFile,
    model: str,
    analyzer: Analyzer = analyze_image,
    file_service: FileIngestionService | None = None,
) -> AnalyzeResponse:
    debug_steps: list[DebugStep] = []
    total_started_at = time.perf_counter()
    suffix = Path(image.filename or "").suffix or ".jpg"
    temp_path: str | None = None
    analysis_path: str | None = None

    try:
        started_at = time.perf_counter()
        payload = await image.read()
        debug_steps.append(DebugStep(label="이미지 업로드", elapsed_ms=elapsed_ms(started_at)))

        if file_service is not None:
            started_at = time.perf_counter()
            stored_file = file_service.store_upload(payload, image.filename)
            stored_image = file_service.get_image(stored_file.file_id, "processed")
            analysis_path = str(stored_image.path)
            debug_steps.append(DebugStep(label="이미지 전처리", elapsed_ms=elapsed_ms(started_at)))
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(payload)
                temp_path = tmp.name
            analysis_path = temp_path

        started_at = time.perf_counter()
        debug_steps.append(DebugStep(label="프롬프트 구성", elapsed_ms=elapsed_ms(started_at)))

        started_at = time.perf_counter()
        result = await run_analyzer_with_timeout(analyzer, analysis_path, model)
        debug_steps.append(DebugStep(label="GPT 분석", elapsed_ms=elapsed_ms(started_at)))

        started_at = time.perf_counter()
        response = AnalyzeResponse(
            model=model,
            result=result,
            debug_steps=debug_steps,
            total_ms=elapsed_ms(total_started_at),
        )
        response.debug_steps.append(DebugStep(label="결과 파싱", elapsed_ms=elapsed_ms(started_at)))
        response.total_ms = elapsed_ms(total_started_at)
        return response
    finally:
        await image.close()
        if temp_path is not None:
            os.unlink(temp_path)


async def stream_analyze_upload(
    image: UploadFile,
    model: str,
    analyzer: Analyzer = analyze_image,
    file_service: FileIngestionService | None = None,
) -> AsyncIterator[str]:
    debug_steps: list[DebugStep] = []
    total_started_at = time.perf_counter()
    suffix = Path(image.filename or "").suffix or ".jpg"
    temp_path: str | None = None
    analysis_path: str | None = None

    try:
        started_at = time.perf_counter()
        payload = await image.read()
        step = DebugStep(label="이미지 업로드", elapsed_ms=elapsed_ms(started_at))
        debug_steps.append(step)
        yield encode_stream_event({"type": "step", "step": step_to_dict(step)})

        if file_service is not None:
            started_at = time.perf_counter()
            stored_file = file_service.store_upload(payload, image.filename)
            stored_image = file_service.get_image(stored_file.file_id, "processed")
            analysis_path = str(stored_image.path)
            step = DebugStep(label="이미지 전처리", elapsed_ms=elapsed_ms(started_at))
            debug_steps.append(step)
            yield encode_stream_event({"type": "step", "step": step_to_dict(step)})
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(payload)
                temp_path = tmp.name
            analysis_path = temp_path

        started_at = time.perf_counter()
        step = DebugStep(label="프롬프트 구성", elapsed_ms=elapsed_ms(started_at))
        debug_steps.append(step)
        yield encode_stream_event({"type": "step", "step": step_to_dict(step)})

        started_at = time.perf_counter()
        result = await run_analyzer_with_timeout(analyzer, analysis_path, model)
        step = DebugStep(label="GPT 분석", elapsed_ms=elapsed_ms(started_at))
        debug_steps.append(step)
        yield encode_stream_event({"type": "step", "step": step_to_dict(step)})

        started_at = time.perf_counter()
        parse_step = DebugStep(label="결과 파싱", elapsed_ms=elapsed_ms(started_at))
        debug_steps.append(parse_step)
        yield encode_stream_event({"type": "step", "step": step_to_dict(parse_step)})

        response = AnalyzeResponse(
            model=model,
            result=result,
            debug_steps=debug_steps,
            total_ms=elapsed_ms(total_started_at),
        )
        yield encode_stream_event({"type": "result", "payload": response_to_dict(response)})
    except Exception as exc:
        yield encode_stream_event({"type": "error", "message": str(exc)})
    finally:
        await image.close()
        if temp_path is not None:
            os.unlink(temp_path)
