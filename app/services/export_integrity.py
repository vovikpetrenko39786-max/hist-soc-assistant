"""Check an exported file's identity before serving it."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class ExportIntegrityError(Exception):
    """Reason is one of: outside_root, missing, corrupt."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


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
    roots = [Path(current_root).resolve()]
    for item in legacy:
        root = Path(item)
        if not root.is_absolute() or root == Path("/"):
            raise ExportIntegrityError("invalid_roots")
        resolved = root.resolve()
        if resolved not in roots:
            roots.append(resolved)
    return roots


def verified_export_path(
    recorded_path: str,
    storage_root: str,
    expected_size: int,
    expected_sha256: str,
) -> Path:
    """Accept only unchanged regular files inside the configured export root."""
    root = Path(storage_root).resolve()
    path = Path(recorded_path).resolve()
    if not path.is_relative_to(root):
        raise ExportIntegrityError("outside_root")
    if not path.is_file():
        raise ExportIntegrityError("missing")
    if path.stat().st_size != expected_size:
        raise ExportIntegrityError("corrupt")
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    if h.hexdigest() != expected_sha256:
        raise ExportIntegrityError("corrupt")
    return path


def verified_export_path_in_roots(
    recorded_path: str,
    roots: list[Path],
    expected_size: int,
    expected_sha256: str,
) -> Path:
    for root in roots:
        try:
            return verified_export_path(
                recorded_path, str(root), expected_size, expected_sha256
            )
        except ExportIntegrityError as exc:
            if exc.reason != "outside_root":
                raise
    raise ExportIntegrityError("outside_root")
