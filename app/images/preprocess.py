from __future__ import annotations

import hashlib
import io
import time
from dataclasses import dataclass, field

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from app.images.profiles import DEFAULT_PROFILE, ImagePreprocessProfile

SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF"}
_HEIF_REGISTERED = False


class ImagePreprocessError(ValueError):
    pass


@dataclass(frozen=True)
class PreprocessStep:
    label: str
    elapsed_ms: int
    children: list["PreprocessStep"] = field(default_factory=list)


@dataclass(frozen=True)
class PreprocessResult:
    original_sha256: str
    processed_sha256: str
    source_mime: str
    source_size: tuple[int, int]
    source_size_bytes: int
    processed_bytes: bytes
    processed_mime: str
    processed_size: tuple[int, int]
    processed_size_bytes: int
    thumbnail_bytes: bytes
    thumbnail_mime: str
    thumbnail_size: tuple[int, int]
    thumbnail_size_bytes: int
    preprocess_profile: str
    steps: list[PreprocessStep]


def calculate_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def register_heif_support() -> None:
    global _HEIF_REGISTERED
    if _HEIF_REGISTERED:
        return
    register_heif_opener()
    _HEIF_REGISTERED = True


def elapsed_ms(started_at: float) -> int:
    return round((time.perf_counter() - started_at) * 1000)


def preprocess_image_bytes(
    image_bytes: bytes,
    *,
    filename: str | None = None,
    profile: ImagePreprocessProfile = DEFAULT_PROFILE,
) -> PreprocessResult:
    original_sha256 = calculate_sha256(image_bytes)
    register_heif_support()

    try:
        with Image.open(io.BytesIO(image_bytes)) as opened:
            source_format = _normalize_format(opened.format, filename)
            if source_format not in SUPPORTED_FORMATS:
                raise ImagePreprocessError(f"지원하지 않는 이미지 형식입니다: {source_format}")

            parent_started_at = time.perf_counter()
            child_steps: list[PreprocessStep] = []

            source_size = opened.size

            started_at = time.perf_counter()
            processed_image = ImageOps.pad(
                opened,
                profile.processed_size,
                method=Image.Resampling.LANCZOS,
                color=profile.background_color,
                centering=(0.5, 0.5),
            )
            child_steps.append(PreprocessStep("사이즈 보정", elapsed_ms(started_at)))

            started_at = time.perf_counter()
            processed_image = _to_srgb_rgb(processed_image, profile.background_color)
            child_steps.append(PreprocessStep("sRGB 변환", elapsed_ms(started_at)))

            started_at = time.perf_counter()
            processed_image = processed_image.copy()
            processed_image.info.clear()
            child_steps.append(PreprocessStep("EXIF 제거", elapsed_ms(started_at)))

            started_at = time.perf_counter()
            processed_bytes = _save_jpeg_bytes(processed_image, profile.quality)
            child_steps.append(PreprocessStep("JPEG 인코딩", elapsed_ms(started_at)))

            started_at = time.perf_counter()
            thumbnail_image = processed_image.resize(profile.thumbnail_size, Image.Resampling.LANCZOS)
            thumbnail_bytes = _save_jpeg_bytes(thumbnail_image, profile.thumbnail_quality)
            child_steps.append(PreprocessStep("썸네일 생성", elapsed_ms(started_at)))

            processed_sha256 = calculate_sha256(processed_bytes)
            steps = [
                PreprocessStep(
                    "이미지 보정",
                    elapsed_ms(parent_started_at),
                    children=child_steps,
                )
            ]

            return PreprocessResult(
                original_sha256=original_sha256,
                processed_sha256=processed_sha256,
                source_mime=_mime_for_format(source_format),
                source_size=source_size,
                source_size_bytes=len(image_bytes),
                processed_bytes=processed_bytes,
                processed_mime=profile.mime,
                processed_size=profile.processed_size,
                processed_size_bytes=len(processed_bytes),
                thumbnail_bytes=thumbnail_bytes,
                thumbnail_mime=profile.mime,
                thumbnail_size=profile.thumbnail_size,
                thumbnail_size_bytes=len(thumbnail_bytes),
                preprocess_profile=profile.name,
                steps=steps,
            )
    except ImagePreprocessError:
        raise
    except (OSError, UnidentifiedImageError) as exc:
        raise ImagePreprocessError("이미지 파일을 열 수 없습니다") from exc


def _normalize_format(image_format: str | None, filename: str | None) -> str:
    if image_format:
        normalized = image_format.upper()
        return "HEIF" if normalized in {"HEIC", "HEIF"} else normalized

    suffix = ""
    if filename:
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "jpg": "JPEG",
        "jpeg": "JPEG",
        "png": "PNG",
        "webp": "WEBP",
        "heic": "HEIF",
        "heif": "HEIF",
    }.get(suffix, "UNKNOWN")


def _mime_for_format(image_format: str) -> str:
    return {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "HEIF": "image/heic",
    }.get(image_format, "application/octet-stream")


def _to_srgb_rgb(image: Image.Image, background_color: str) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, background_color)
        return Image.alpha_composite(background, rgba).convert("RGB")

    icc_profile = image.info.get("icc_profile")
    if icc_profile:
        try:
            source_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
            srgb_profile = ImageCms.createProfile("sRGB")
            return ImageCms.profileToProfile(
                image,
                source_profile,
                srgb_profile,
                outputMode="RGB",
            )
        except (ImageCms.PyCMSError, OSError, ValueError):
            pass

    return image.convert("RGB")


def _save_jpeg_bytes(image: Image.Image, quality: int) -> bytes:
    output = io.BytesIO()
    image.save(
        output,
        format="JPEG",
        quality=quality,
        optimize=False,
        progressive=False,
    )
    return output.getvalue()
