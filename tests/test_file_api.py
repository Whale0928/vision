from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def make_jpeg_bytes() -> bytes:
    from PIL import Image

    image = Image.new("RGB", (640, 480), (84, 104, 96))
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def make_heif_bytes() -> bytes:
    from PIL import Image
    from pillow_heif import register_heif_opener

    register_heif_opener()
    image = Image.new("RGB", (640, 480), (84, 104, 96))
    output = io.BytesIO()
    image.save(output, format="HEIF")
    return output.getvalue()


class FileAPITest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name)
        self.client = TestClient(create_app(data_dir=self.data_dir))

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_post_file_stores_original_processed_thumbnail_and_db_row(self):
        image_bytes = make_jpeg_bytes()

        response = self.client.post(
            "/api/files",
            files={"image": ("label.jpg", image_bytes, "image/jpeg")},
        )

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertFalse(body["duplicate"])
        self.assertEqual("processed_saved", body["status"])
        self.assertTrue(body["file_id"].startswith("file_"))
        self.assertIn("/api/files/", body["original_url"])
        self.assertIn("/api/files/", body["processed_url"])
        self.assertIn("/api/files/", body["thumbnail_url"])
        self.assertEqual("이미지 보정", body["steps"][2]["label"])
        self.assertEqual(
            ["사이즈 보정", "sRGB 변환", "EXIF 제거", "JPEG 인코딩", "썸네일 생성"],
            [child["label"] for child in body["steps"][2]["children"]],
        )

        file_id = body["file_id"]
        for kind in ("original", "processed", "thumbnail"):
            image_response = self.client.get(f"/api/files/{file_id}/{kind}")
            self.assertEqual(200, image_response.status_code, image_response.text)
            self.assertIn("image/", image_response.headers["content-type"])
            self.assertGreater(len(image_response.content), 100)

        detail = self.client.get(f"/api/files/{file_id}").json()
        self.assertEqual(file_id, detail["file_id"])
        self.assertEqual("label.jpg", detail["original_filename"])
        self.assertEqual(1024, detail["processed"]["width"])
        self.assertEqual(1365, detail["processed"]["height"])

        listing = self.client.get("/api/files").json()
        self.assertEqual(1, len(listing["items"]))
        self.assertEqual(file_id, listing["items"][0]["file_id"])
        self.assertIn("/api/files/", listing["items"][0]["thumbnail_url"])

    def test_post_heif_file_stores_processed_jpeg(self):
        image_bytes = make_heif_bytes()

        response = self.client.post(
            "/api/files",
            files={"image": ("label.heic", image_bytes, "image/heic")},
        )

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        file_id = body["file_id"]

        detail = self.client.get(f"/api/files/{file_id}").json()
        self.assertEqual("image/heic", detail["source"]["mime"])
        self.assertEqual("image/jpeg", detail["processed"]["mime"])
        self.assertEqual(1024, detail["processed"]["width"])
        self.assertEqual(1365, detail["processed"]["height"])

    def test_duplicate_upload_reuses_existing_file_id(self):
        image_bytes = make_jpeg_bytes()

        first = self.client.post(
            "/api/files",
            files={"image": ("label.jpg", image_bytes, "image/jpeg")},
        ).json()
        second = self.client.post(
            "/api/files",
            files={"image": ("same-name.jpg", image_bytes, "image/jpeg")},
        ).json()

        self.assertEqual(first["file_id"], second["file_id"])
        self.assertTrue(second["duplicate"])
        self.assertEqual("processed_saved", second["status"])

        listing = self.client.get("/api/files").json()
        self.assertEqual(1, len(listing["items"]))

    def test_image_preprocess_sample_page_is_served(self):
        response = self.client.get("/image-preprocess")

        self.assertEqual(200, response.status_code)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("이미지 저장", response.text)
        self.assertIn("/api/files", response.text)
        self.assertIn('href="/"', response.text)
        self.assertIn("upload-preview", response.text)
        self.assertIn("replace-action", response.text)
        self.assertIn(".upload-empty[hidden]", response.text)
        self.assertIn("formatDuration(step.elapsed_ms)", response.text)
        self.assertNotIn("const FIXED_TIME_LABEL", response.text)
        self.assertNotIn("0.2초 (200ms)", response.text)
        self.assertNotIn("await showDetail(payload.file_id)", response.text)

    def test_top_level_pages_link_to_each_other(self):
        index_response = self.client.get("/")
        preprocess_response = self.client.get("/image-preprocess")

        self.assertEqual(200, index_response.status_code)
        self.assertEqual(200, preprocess_response.status_code)
        self.assertIn('href="/image-preprocess"', index_response.text)
        self.assertIn('href="/"', preprocess_response.text)


if __name__ == "__main__":
    unittest.main()
