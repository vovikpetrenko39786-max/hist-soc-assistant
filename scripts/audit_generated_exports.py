"""Read-only aggregate inventory of generated exports.

Run inside the application environment where PostgreSQL and stored files are
accessible. No database writes, no file modifications, no paths or secrets in
stdout. Take a separate verified database and volume backup before migration.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from collections import Counter
from pathlib import Path


def classify_export(row, root: Path) -> str:
    """Classify one export without disclosing its name/path."""
    p = Path(row.file_path).resolve()
    if not p.is_relative_to(root.resolve()):
        return "outside_storage_root"
    if not p.is_file():
        return "missing"
    try:
        if p.stat().st_size != row.size_bytes:
            return "size_mismatch"
        sha = hashlib.sha256()
        with p.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                sha.update(block)
        if sha.hexdigest() != row.sha256:
            return "hash_mismatch"
    except OSError:
        return "unreadable"
    return "healthy"


async def run() -> None:
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.session import SessionLocal, engine
    from app.models.entities import ExportedFile

    settings = get_settings()
    root = Path(settings.output_storage_dir).resolve()
    counts: Counter[str] = Counter()
    async with SessionLocal() as session:
        results = await session.stream_scalars(select(ExportedFile))
        async for row in results:
            counts[classify_export(row, root)] += 1
    print(json.dumps({
        "total": sum(counts.values()),
        "classification_counts": dict(sorted(counts.items())),
        "ready_for_storage_migration": False,
        "note": "Inventory only. Back up database and old files before moving paths.",
    }, ensure_ascii=False, indent=2))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
