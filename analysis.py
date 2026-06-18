"""이미지 1장 → 위스키 라벨 분석 (실제 GPT 호출).

ai/prompt.txt + ai/response_schema.json 을 사용해 Structured Outputs 로 받는다.
클라이언트는 최초 1회만 기동(health check)하고 재사용한다.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from openai import OpenAI

from gpt_client import launch_gpt

ROOT = Path(__file__).resolve().parent
_PROMPT_PATH = ROOT / "ai" / "prompt.txt"
_SCHEMA_PATH = ROOT / "ai" / "response_schema.json"
_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    # 최초 1회만 기동(연결 핑퐁), 이후 재사용
    global _client
    if _client is None:
        _client = launch_gpt()
    return _client


def analyze_image(image_path: str, model: str = "gpt-4o-mini", detail: str = "high") -> dict:
    # 이미지 라벨을 분석해 스키마에 맞는 dict 반환
    prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

    path = Path(image_path)
    mime = _MIME.get(path.suffix.lower(), "image/jpeg")
    b64 = base64.b64encode(path.read_bytes()).decode()

    resp = _get_client().responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime};base64,{b64}",
                        "detail": detail,
                    },
                ],
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "WhiskyAnalysisResponse",
                "schema": schema,
                "strict": True,
            }
        },
    )
    return json.loads(resp.output_text)
