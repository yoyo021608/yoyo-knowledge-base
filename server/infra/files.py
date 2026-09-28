import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4


class FileNotFoundInStorageError(FileNotFoundError):
    pass


class FileIntegrityError(OSError):
    pass


@dataclass(frozen=True, slots=True)
class FileObject:
    id: str
    name: str
    content_type: str
    size: int
    checksum: str
    created_at: datetime


class LocalFileStorage:
    """Stores bytes and immutable metadata below a configured directory."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def put(self, name: str, content: bytes, content_type: str) -> FileObject:
        safe_name = Path(name).name.strip()
        if not safe_name or safe_name != name:
            raise ValueError("file name must be a plain file name")
        if not content_type.strip():
            raise ValueError("content type cannot be empty")

        file_id = str(uuid4())
        descriptor = FileObject(
            id=file_id,
            name=safe_name,
            content_type=content_type,
            size=len(content),
            checksum=hashlib.sha256(content).hexdigest(),
            created_at=datetime.now(UTC),
        )
        data_path, metadata_path = self._paths(file_id)
        self._atomic_write(data_path, content)
        metadata = json.dumps(
            {**asdict(descriptor), "created_at": descriptor.created_at.isoformat()},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            self._atomic_write(metadata_path, metadata)
        except BaseException:
            data_path.unlink(missing_ok=True)
            raise
        return descriptor

    def get(self, file_id: str) -> tuple[bytes, FileObject]:
        data_path, metadata_path = self._paths(file_id)
        if not data_path.is_file() or not metadata_path.is_file():
            raise FileNotFoundInStorageError(file_id)

        content = data_path.read_bytes()
        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        descriptor = FileObject(
            id=str(raw["id"]),
            name=str(raw["name"]),
            content_type=str(raw["content_type"]),
            size=int(raw["size"]),
            checksum=str(raw["checksum"]),
            created_at=datetime.fromisoformat(str(raw["created_at"])),
        )
        if descriptor.id != file_id:
            raise FileIntegrityError(f"stored file {file_id} has mismatched metadata")
        checksum = hashlib.sha256(content).hexdigest()
        if descriptor.size != len(content) or descriptor.checksum != checksum:
            raise FileIntegrityError(
                f"stored file {file_id} failed integrity validation"
            )
        return content, descriptor

    def delete(self, file_id: str) -> None:
        data_path, metadata_path = self._paths(file_id)
        data_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)

    def _paths(self, file_id: str) -> tuple[Path, Path]:
        normalized_id = str(UUID(file_id))
        return (
            self._root / f"{normalized_id}.data",
            self._root / f"{normalized_id}.json",
        )

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        temporary_path = path.with_suffix(f"{path.suffix}.{uuid4()}.tmp")
        try:
            with temporary_path.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)
