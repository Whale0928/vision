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
