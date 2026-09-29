from pathlib import Path

import pytest

from server.infra.files import (
    FileIntegrityError,
    FileNotFoundInStorageError,
    LocalFileStorage,
)


def test_file_round_trip_and_delete(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)

    descriptor = storage.put("notes.md", b"knowledge", "text/markdown")
    content, loaded_descriptor = storage.get(descriptor.id)

    assert content == b"knowledge"
    assert loaded_descriptor == descriptor

    storage.delete(descriptor.id)
    with pytest.raises(FileNotFoundInStorageError):
        storage.get(descriptor.id)


def test_file_name_cannot_escape_storage_root(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)

    with pytest.raises(ValueError):
        storage.put("../outside.md", b"content", "text/markdown")


def test_file_integrity_is_checked_on_read(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    descriptor = storage.put("notes.md", b"knowledge", "text/markdown")
    (tmp_path / f"{descriptor.id}.data").write_bytes(b"tampered")

    with pytest.raises(FileIntegrityError):
        storage.get(descriptor.id)
