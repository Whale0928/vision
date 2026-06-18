from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class FileRecord(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False, index=True)
    original_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    source_mime: Mapped[str] = mapped_column(String, nullable=False)
    source_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    source_width: Mapped[int] = mapped_column(Integer, nullable=False)
    source_height: Mapped[int] = mapped_column(Integer, nullable=False)
    original_object_path: Mapped[str] = mapped_column(String, nullable=False)
    original_sha256: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    processed_object_path: Mapped[str] = mapped_column(String, nullable=False)
    processed_sha256: Mapped[str] = mapped_column(String, nullable=False, index=True)
    processed_mime: Mapped[str] = mapped_column(String, nullable=False)
    processed_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_width: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_height: Mapped[int] = mapped_column(Integer, nullable=False)
    thumbnail_object_path: Mapped[str] = mapped_column(String, nullable=False)
    thumbnail_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    preprocess_profile: Mapped[str] = mapped_column(String, nullable=False)
    original_saved_at: Mapped[str] = mapped_column(String, nullable=False)
    processed_saved_at: Mapped[str] = mapped_column(String, nullable=False)
