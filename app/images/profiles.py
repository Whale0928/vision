from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImagePreprocessProfile:
    name: str
    processed_size: tuple[int, int]
    thumbnail_size: tuple[int, int]
    background_color: str
    image_format: str
    mime: str
    quality: int
    thumbnail_quality: int


DEFAULT_PROFILE = ImagePreprocessProfile(
    name="jpeg_1024x1365_q90",
    processed_size=(1024, 1365),
    thumbnail_size=(320, 426),
    background_color="#FFFFFF",
    image_format="JPEG",
    mime="image/jpeg",
    quality=90,
    thumbnail_quality=90,
)
