from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base


@dataclass(frozen=True)
class Database:
    engine: Engine
    session_factory: sessionmaker[Session]

    def init_schema(self) -> None:
        Base.metadata.create_all(self.engine)


def create_database(db_path: Path) -> Database:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    database = Database(engine=engine, session_factory=sessionmaker(bind=engine, expire_on_commit=False))
    database.init_schema()
    return database
