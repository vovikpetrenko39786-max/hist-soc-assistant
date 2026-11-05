"""Check an exported file's identity before serving it."""
from __future__ import annotations

import hashlib
from pathlib import Path


class ExportIntegrityError(Exception):
    """Reason is one of: outside_root, missing, corrupt."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


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
