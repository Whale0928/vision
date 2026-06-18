from __future__ import annotations

import hashlib
import io
import unittest


def make_image_bytes(
    *,
    mode: str = "RGB",
    size: tuple[int, int] = (800, 600),
    color: tuple[int, ...] = (84, 104, 96),
    image_format: str = "JPEG",
    exif_orientation: int | None = None,
) -> bytes:
    from PIL import Image

    image = Image.new(mode, size, color)
    output = io.BytesIO()
    save_kwargs = {}
    if exif_orientation is not None:
        exif = Image.Exif()
        exif[274] = exif_orientation
        save_kwargs["exif"] = exif
    image.save(output, format=image_format, **save_kwargs)
    return output.getvalue()


def make_heif_bytes() -> bytes:
    from PIL import Image
    from pillow_heif import register_heif_opener

    register_heif_opener()
    image = Image.new("RGB", (320, 240), (84, 104, 96))
    output = io.BytesIO()
    image.save(output, format="HEIF")
    return output.getvalue()


class ImagePreprocessTest(unittest.TestCase):
    def test_preprocess_jpeg_returns_standard_images_and_hashes(self):
        from PIL import Image

        from app.images.preprocess import preprocess_image_bytes
        from app.images.profiles import DEFAULT_PROFILE

        image_bytes = make_image_bytes()

        result = preprocess_image_bytes(image_bytes, filename="label.jpg")

        self.assertEqual(hashlib.sha256(image_bytes).hexdigest(), result.original_sha256)
        self.assertEqual(DEFAULT_PROFILE.name, result.preprocess_profile)
        self.assertEqual("image/jpeg", result.source_mime)
        self.assertEqual("image/jpeg", result.processed_mime)
        self.assertEqual("image/jpeg", result.thumbnail_mime)
        self.assertEqual(hashlib.sha256(result.processed_bytes).hexdigest(), result.processed_sha256)

        with Image.open(io.BytesIO(result.processed_bytes)) as processed:
            self.assertEqual(DEFAULT_PROFILE.processed_size, processed.size)
            self.assertEqual("RGB", processed.mode)
            self.assertEqual("JPEG", processed.format)
            self.assertEqual(0, len(processed.getexif()))

        with Image.open(io.BytesIO(result.thumbnail_bytes)) as thumbnail:
            self.assertEqual(DEFAULT_PROFILE.thumbnail_size, thumbnail.size)
            self.assertEqual("RGB", thumbnail.mode)
            self.assertEqual("JPEG", thumbnail.format)

        step_labels = [step.label for step in result.steps]
        self.assertIn("이미지 보정", step_labels)
        preprocess_step = next(step for step in result.steps if step.label == "이미지 보정")
        self.assertEqual(
            ["사이즈 보정", "sRGB 변환", "EXIF 제거", "JPEG 인코딩", "썸네일 생성"],
            [child.label for child in preprocess_step.children],
        )

    def test_transparent_png_is_flattened_to_white_rgb_jpeg(self):
        from PIL import Image

        from app.images.preprocess import preprocess_image_bytes

        image_bytes = make_image_bytes(
            mode="RGBA",
            size=(100, 100),
            color=(0, 0, 0, 0),
            image_format="PNG",
        )

        result = preprocess_image_bytes(image_bytes, filename="transparent.png")

        with Image.open(io.BytesIO(result.processed_bytes)) as processed:
            self.assertEqual("RGB", processed.mode)
            self.assertEqual((255, 255, 255), processed.getpixel((0, 0)))

    def test_exif_orientation_is_not_applied_but_metadata_is_removed(self):
        from PIL import Image

        from app.images.preprocess import preprocess_image_bytes

        image_bytes = make_image_bytes(size=(40, 20), exif_orientation=6)

        result = preprocess_image_bytes(image_bytes, filename="rotated.jpg")

        self.assertEqual((40, 20), result.source_size)
        with Image.open(io.BytesIO(result.processed_bytes)) as processed:
            self.assertEqual(0, len(processed.getexif()))

    def test_heif_image_is_processed_to_standard_jpeg(self):
        from PIL import Image

        from app.images.preprocess import preprocess_image_bytes
        from app.images.profiles import DEFAULT_PROFILE

        image_bytes = make_heif_bytes()

        result = preprocess_image_bytes(image_bytes, filename="label.heic")

        self.assertEqual("image/heic", result.source_mime)
        self.assertEqual((320, 240), result.source_size)
        self.assertEqual("image/jpeg", result.processed_mime)
        with Image.open(io.BytesIO(result.processed_bytes)) as processed:
            self.assertEqual(DEFAULT_PROFILE.processed_size, processed.size)
            self.assertEqual("JPEG", processed.format)

    def test_heif_opener_is_registered_for_pillow(self):
        from PIL import Image

        from app.images.preprocess import register_heif_support

        register_heif_support()
        Image.init()

        self.assertEqual("HEIF", Image.EXTENSION[".heic"])
        self.assertEqual("HEIF", Image.EXTENSION[".heif"])

    def test_invalid_image_bytes_raise_preprocess_error(self):
        from app.images.preprocess import ImagePreprocessError, preprocess_image_bytes

        with self.assertRaises(ImagePreprocessError):
            preprocess_image_bytes(b"not-an-image", filename="broken.jpg")


if __name__ == "__main__":
    unittest.main()
