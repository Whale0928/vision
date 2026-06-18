from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fs.osfs import OSFS


@dataclass
class ObjectStore:
    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.fs = OSFS(str(self.root), create=True)

    def write_bytes(self, object_path: str, payload: bytes) -> int:
        directory = object_path.rsplit("/", 1)[0]
        self.fs.makedirs(directory, recreate=True)
        self.fs.writebytes(object_path, payload)
        return len(payload)

    def system_path(self, object_path: str) -> Path:
        return Path(self.fs.getsyspath(object_path))

    def exists(self, object_path: str) -> bool:
        return self.fs.exists(object_path)
