"""Fail closed when a stored export cannot be safely served."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class ExportIntegrityError(ValueError):
    """An export is missing, unsafe, or differs from its recorded metadata."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _is_filesystem_root(path: Path) -> bool:
    return path.parent == path


def storage_roots(current_root: str, legacy_roots_json: str | None = None) -> list[Path]:
    """Return explicit read roots without broadening writes to legacy storage."""
    try:
        legacy = json.loads(legacy_roots_json or "[]")
    except (TypeError, ValueError) as exc:
        raise ExportIntegrityError("invalid_roots") from exc
    if not isinstance(legacy, list) or len(legacy) > 8 or not all(
        isinstance(item, str) and item.strip() for item in legacy
    ):
        raise ExportIntegrityError("invalid_roots")

    current = Path(current_root).resolve()
    if _is_filesystem_root(current):
        raise ExportIntegrityError("invalid_roots")
    roots = [current]
    for item in legacy:
        root = Path(item)
        if not root.is_absolute():
            raise ExportIntegrityError("invalid_roots")
        resolved = root.resolve()
        if _is_filesystem_root(resolved):
            raise ExportIntegrityError("invalid_roots")
        if resolved not in roots:
            roots.append(resolved)
    return roots


def verified_export_path(
    recorded_path: str,
    storage_root: str | None = None,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
    *,
    storage_dir: str | None = None,
    file_format: str | None = None,
) -> Path:
    """Resolve a persisted export inside storage and verify its format and bytes."""
    root_value = storage_dir if storage_dir is not None else storage_root
    if not root_value:
        raise ExportIntegrityError("invalid_root")
    if storage_dir is not None and storage_root is not None:
        raise ExportIntegrityError("invalid_root")
    if file_format is not None and file_format not in {"docx", "pdf"}:
        raise ExportIntegrityError("unsupported_format")

    root = Path(root_value).resolve()
    if _is_filesystem_root(root):
        raise ExportIntegrityError("invalid_root")
    path = Path(recorded_path).resolve()
    if path == root or not path.is_relative_to(root):
        raise ExportIntegrityError("outside_root")
    if file_format is not None and path.suffix.lower() != f".{file_format}":
        raise ExportIntegrityError("format_mismatch")
    if not path.is_file():
        raise ExportIntegrityError("missing")
    if expected_size is None or path.stat().st_size != expected_size:
        raise ExportIntegrityError("corrupt")
    if (
        not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in expected_sha256)
    ):
        raise ExportIntegrityError("corrupt")

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected_sha256.lower():
        raise ExportIntegrityError("corrupt")
    return path


def verified_export_path_in_roots(
    recorded_path: str,
    roots: list[Path],
    expected_size: int | None,
    expected_sha256: str | None,
    *,
    file_format: str | None = None,
) -> Path:
    """Verify an export against the current root and explicitly allowed legacy roots."""
    for root in roots:
        try:
            return verified_export_path(
                recorded_path,
                str(root),
                expected_size,
                expected_sha256,
                file_format=file_format,
            )
        except ExportIntegrityError as exc:
            if exc.reason != "outside_root":
                raise
    raise ExportIntegrityError("outside_root")
