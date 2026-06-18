from __future__ import annotations

from sqlalchemy import select

from app.db.models import FileRecord
from app.db.session import Database


class FileRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def find_by_original_sha256(self, original_sha256: str) -> FileRecord | None:
        with self.database.session_factory() as session:
            return session.scalar(select(FileRecord).where(FileRecord.original_sha256 == original_sha256))

    def find_by_id(self, file_id: str) -> FileRecord | None:
        with self.database.session_factory() as session:
            return session.get(FileRecord, file_id)

    def list_recent(self, limit: int = 40) -> list[FileRecord]:
        with self.database.session_factory() as session:
            return list(
                session.scalars(
                    select(FileRecord).order_by(FileRecord.created_at.desc()).limit(limit)
                )
            )

    def insert(self, record: FileRecord) -> FileRecord:
        with self.database.session_factory() as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
