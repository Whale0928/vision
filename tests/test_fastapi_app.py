from __future__ import annotations

import unittest

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


def fake_analyzer(image_path: str, model: str) -> dict:
    assert image_path
    assert model == "gpt-4o-mini"
    return SAMPLE_RESULT


class FastAPIAppTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app(analyzer=fake_analyzer))

    def test_index_serves_dashboard_html(self):
        response = self.client.get("/")

        self.assertEqual(200, response.status_code)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("위스키 라벨 분석", response.text)
        self.assertIn("panel-shell", response.text)
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
            files={"image": ("label.png", b"fake-image", "image/png")},
        )

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual(SAMPLE_RESULT["eng_name"], body["result"]["eng_name"])
        self.assertEqual("gpt-4o-mini", body["model"])
        self.assertGreaterEqual(body["total_ms"], 0)
        self.assertGreaterEqual(len(body["debug_steps"]), 3)
        self.assertEqual("이미지 업로드", body["debug_steps"][0]["label"])
        self.assertIn("GPT 분석", {step["label"] for step in body["debug_steps"]})


if __name__ == "__main__":
    unittest.main()
