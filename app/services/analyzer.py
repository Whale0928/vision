from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from analysis import analyze_image
from app.schemas import AnalyzeResponse, DebugStep

Analyzer = Callable[[str, str], dict[str, Any]]


def elapsed_ms(started_at: float) -> int:
    return round((time.perf_counter() - started_at) * 1000)


async def analyze_upload(
    image: UploadFile,
    model: str,
    analyzer: Analyzer = analyze_image,
) -> AnalyzeResponse:
    debug_steps: list[DebugStep] = []
    total_started_at = time.perf_counter()
    suffix = Path(image.filename or "").suffix or ".jpg"
    temp_path: str | None = None

    try:
        started_at = time.perf_counter()
        payload = await image.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(payload)
            temp_path = tmp.name
        debug_steps.append(DebugStep(label="이미지 업로드", elapsed_ms=elapsed_ms(started_at)))

        started_at = time.perf_counter()
        debug_steps.append(DebugStep(label="프롬프트 구성", elapsed_ms=elapsed_ms(started_at)))

        started_at = time.perf_counter()
        result = await run_in_threadpool(analyzer, temp_path, model)
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
