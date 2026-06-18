from __future__ import annotations

import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


SAMPLE_RESULT = {
    "is_whisky": True,
    "label_legible": True,
    "visible_text_raw": "THE GLENALLACHIE",
    "eng_name": "The GlenAllachie 17 Year Old",
    "kor_name": "글렌알라키 17년",
    "type": "WHISKY",
    "category_group": "SINGLE_MALT",
    "abv": 50,
    "age": 17,
    "cask": "Mizunara & Oloroso Sherry",
    "volume_ml": 700,
    "country": "Scotland",
    "distillery": "GlenAllachie",
    "identification_reason": "라벨 텍스트로 식별했다.",
    "identification": "이 위스키는 GlenAllachie 17이다.",
    "description": "스페이사이드 싱글 몰트.",
}


def make_jpeg_bytes() -> bytes:
    from PIL import Image

    image = Image.new("RGB", (640, 480), (84, 104, 96))
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


class FastAPIAppTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name)
        self.analyzer_calls: list[dict] = []
        self.client = TestClient(create_app(analyzer=self.fake_analyzer, data_dir=self.data_dir))

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def fake_analyzer(self, image_path: str, model: str) -> dict:
        from PIL import Image

        with Image.open(image_path) as image:
            self.analyzer_calls.append(
                {
                    "image_path": image_path,
                    "model": model,
                    "format": image.format,
                    "size": image.size,
                }
            )
        return SAMPLE_RESULT

    def test_index_serves_dashboard_html(self):
        response = self.client.get("/")

        self.assertEqual(200, response.status_code)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("위스키 라벨 분석", response.text)
        self.assertIn("panel-shell", response.text)
        self.assertIn("analysis-upload-empty", response.text)
        self.assertIn("replace-action", response.text)
        self.assertIn("/static/css/app.css", response.text)
        self.assertIn("/static/js/app.js", response.text)
        self.assertNotIn("resource/image/", response.text)

    def test_static_font_is_served(self):
        response = self.client.get("/static/fonts/PretendardVariable.woff2")

        self.assertEqual(200, response.status_code)
        self.assertGreater(len(response.content), 1000)

    def test_analyze_upload_returns_result_with_debug_steps(self):
        response = self.client.post(
            "/api/analyze",
            data={"model": "gpt-4o-mini"},
            files={"image": ("label.jpg", make_jpeg_bytes(), "image/jpeg")},
        )

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual(SAMPLE_RESULT["eng_name"], body["result"]["eng_name"])
        self.assertEqual("gpt-4o-mini", body["model"])
        self.assertGreaterEqual(body["total_ms"], 0)
        self.assertGreaterEqual(len(body["debug_steps"]), 5)
        self.assertEqual("이미지 업로드", body["debug_steps"][0]["label"])
        self.assertIn("이미지 전처리", {step["label"] for step in body["debug_steps"]})
        self.assertIn("GPT 분석", {step["label"] for step in body["debug_steps"]})
        self.assertEqual(1, len(self.analyzer_calls))
        self.assertEqual("JPEG", self.analyzer_calls[0]["format"])
        self.assertEqual((1024, 1365), self.analyzer_calls[0]["size"])
        self.assertIn("/objects/files/processed/", self.analyzer_calls[0]["image_path"])

    def test_analysis_frontend_has_progressive_debug_blocks(self):
        script = self.client.get("/static/js/app.js")
        styles = self.client.get("/static/css/app.css")

        self.assertEqual(200, script.status_code)
        self.assertEqual(200, styles.status_code)
        self.assertIn("/api/analyze/stream", script.text)
        self.assertIn("readAnalysisStream", script.text)
        self.assertIn("DEBUG_STEP_FLOW", script.text)
        self.assertIn("playDebugProgress", script.text)
        self.assertIn(".debug-row.running", styles.text)
        self.assertIn(".debug-row.completed", styles.text)
        self.assertIn(".upload-empty[hidden]", styles.text)
        self.assertIn("function formatDuration(ms)", script.text)
        self.assertIn("formatDuration(step.elapsed_ms)", script.text)
        self.assertIn("formatDuration(totalMs)", script.text)
        self.assertIn("grid-template-rows: auto auto", styles.text)
        self.assertNotIn("FIXED_TIME_LABEL", script.text)
        self.assertNotIn("0.2초 (200ms)", styles.text)
        self.assertNotIn("milliseconds", self.client.get("/").text)
        self.assertNotIn("0.2초 (200ms)", self.client.get("/").text)
        self.assertNotIn("debug-track", script.text)
        self.assertNotIn("elapsed_ms)}ms", script.text)

    def test_analyze_stream_emits_steps_before_result(self):
        with self.client.stream(
            "POST",
            "/api/analyze/stream",
            data={"model": "gpt-4o-mini"},
            files={"image": ("label.jpg", make_jpeg_bytes(), "image/jpeg")},
        ) as response:
            self.assertEqual(200, response.status_code)
            events = [json.loads(line) for line in response.iter_lines() if line]

        self.assertGreaterEqual(len(events), 6)
        self.assertEqual("step", events[0]["type"])
        self.assertEqual("이미지 업로드", events[0]["step"]["label"])
        self.assertEqual("step", events[1]["type"])
        self.assertEqual("이미지 전처리", events[1]["step"]["label"])
        self.assertEqual("result", events[-1]["type"])
        self.assertEqual(SAMPLE_RESULT["eng_name"], events[-1]["payload"]["result"]["eng_name"])
        self.assertEqual("JPEG", self.analyzer_calls[-1]["format"])
        self.assertEqual((1024, 1365), self.analyzer_calls[-1]["size"])

    def test_analyze_reuses_processed_file_for_same_image_with_different_model(self):
        image_bytes = make_jpeg_bytes()

        first = self.client.post(
            "/api/analyze",
            data={"model": "gpt-4o-mini"},
            files={"image": ("label.jpg", image_bytes, "image/jpeg")},
        )
        second = self.client.post(
            "/api/analyze",
            data={"model": "gpt-5.5"},
            files={"image": ("label.jpg", image_bytes, "image/jpeg")},
        )

        self.assertEqual(200, first.status_code, first.text)
        self.assertEqual(200, second.status_code, second.text)
        self.assertEqual(2, len(self.analyzer_calls))
        self.assertEqual("gpt-4o-mini", self.analyzer_calls[0]["model"])
        self.assertEqual("gpt-5.5", self.analyzer_calls[1]["model"])
        self.assertEqual(self.analyzer_calls[0]["image_path"], self.analyzer_calls[1]["image_path"])

    def test_analyze_stream_returns_error_when_analyzer_times_out(self):
        previous_timeout = os.environ.get("VISION_ANALYSIS_TIMEOUT_SECONDS")
        os.environ["VISION_ANALYSIS_TIMEOUT_SECONDS"] = "0.001"

        def slow_analyzer(image_path: str, model: str) -> dict:
            time.sleep(0.05)
            return SAMPLE_RESULT

        try:
            client = TestClient(create_app(analyzer=slow_analyzer, data_dir=self.data_dir / "timeout"))
            with client.stream(
                "POST",
                "/api/analyze/stream",
                data={"model": "gpt-4o-mini"},
                files={"image": ("label.jpg", make_jpeg_bytes(), "image/jpeg")},
            ) as response:
                self.assertEqual(200, response.status_code)
                events = [json.loads(line) for line in response.iter_lines() if line]
        finally:
            if previous_timeout is None:
                os.environ.pop("VISION_ANALYSIS_TIMEOUT_SECONDS", None)
            else:
                os.environ["VISION_ANALYSIS_TIMEOUT_SECONDS"] = previous_timeout

        self.assertEqual("error", events[-1]["type"])
        self.assertIn("분석 시간이 초과", events[-1]["message"])


if __name__ == "__main__":
    unittest.main()
