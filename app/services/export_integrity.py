"""Fail closed when a stored export cannot be safely served."""
from __future__ import annotations

import hashlib
from pathlib import Path


class ExportIntegrityError(ValueError):
    """An export is missing, unsafe, or differs from its recorded metadata."""


def verified_export_path(
    file_path: str,
    *,
    storage_dir: str,
    file_format: str,
    expected_size: int,
    expected_sha256: str,
) -> Path:
    """Resolve a persisted export only inside its storage root and verify its bytes."""
    if file_format not in {"docx", "pdf"}:
        raise ExportIntegrityError("Unsupported export format")
    root = Path(storage_dir).resolve()
    candidate = Path(file_path).resolve()
    if not candidate.is_relative_to(root) or candidate == root:
        raise ExportIntegrityError("Export path is outside output storage")
    if candidate.suffix.lower() != f".{file_format}":
        raise ExportIntegrityError("Export extension does not match its format")
    if not candidate.is_file():
        raise ExportIntegrityError("Export file is missing")
    if expected_size is None or candidate.stat().st_size != expected_size:
        raise ExportIntegrityError("Export size does not match its record")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ExportIntegrityError("Export checksum is missing or invalid")
    digest = hashlib.sha256()
    with candidate.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256.lower():
        raise ExportIntegrityError("Export checksum mismatch")
    return candidate
