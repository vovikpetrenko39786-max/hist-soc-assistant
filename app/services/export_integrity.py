"""Validate persisted export paths and bytes before serving them."""
from __future__ import annotations

import hashlib
from pathlib import Path


class ExportIntegrityError(ValueError):
    """A stored export is missing, outside storage, or differs from metadata."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def verified_export_path(
    recorded_path: str,
    storage_root: str,
    expected_size: int | None,
    expected_sha256: str | None,
    *,
    file_format: str,
) -> Path:
    """Resolve an export inside ``storage_root`` and verify suffix, size and SHA-256."""
    if file_format not in {"docx", "pdf"}:
        raise ExportIntegrityError("unsupported_format")

    root = Path(storage_root).resolve()
    if root.parent == root:
        raise ExportIntegrityError("invalid_root")

    try:
        path = Path(recorded_path).resolve()
    except OSError as exc:
        raise ExportIntegrityError("unavailable") from exc
    if path == root or not path.is_relative_to(root):
        raise ExportIntegrityError("outside_root")
    if path.suffix.lower() != f".{file_format}":
        raise ExportIntegrityError("format_mismatch")
    try:
        if not path.is_file():
            raise ExportIntegrityError("missing")
        if expected_size is None or path.stat().st_size != expected_size:
            raise ExportIntegrityError("corrupt")
    except OSError as exc:
        raise ExportIntegrityError("unavailable") from exc
    if (
        not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in expected_sha256)
    ):
        raise ExportIntegrityError("corrupt")

    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ExportIntegrityError("unavailable") from exc
    if digest.hexdigest() != expected_sha256.lower():
        raise ExportIntegrityError("corrupt")
    return path
