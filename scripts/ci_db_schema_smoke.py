"""Smoke-test the Hist-Soc schema against a disposable CI PostgreSQL database.

Fail closed if this script is inadvertently run with any other database.
No production credentials, database migration, or existing data are used.
"""
from __future__ import annotations

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


def validated_ci_database_url(raw: str | None) -> str:
    if not raw:
        raise RuntimeError("DATABASE_URL must be the dedicated CI URL")
    try:
        url = make_url(raw)
    except Exception as exc:
        raise RuntimeError("Invalid CI database URL") from exc
    if (url.drivername != "postgresql+asyncpg"
            or url.host != "127.0.0.1"
            or url.port != 5432
            or url.database != "hist_soc_ci"
            or url.username != "ci"
            or url.password != "ci_test"
            or url.query):
        raise RuntimeError("Refusing database other than isolated 127.0.0.1/hist_soc_ci")
    return raw


async def main() -> None:
    url = validated_ci_database_url(os.getenv("DATABASE_URL"))
    import app.models  # noqa: F401
    from app.db.base import Base

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
            result = await conn.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            ))
            tables = {row[0] for row in result}
            needed = {
                "teachers", "class_groups", "class_courses", "lessons",
                "source_chunks", "generation_runs", "exported_files",
            }
            missing = needed - tables
            if missing:
                raise RuntimeError("CI database schema missing required tables: "
                                   + ", ".join(sorted(missing)))
            vector = await conn.scalar(text(
                "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
            ))
            if not vector:
                raise RuntimeError("CI pgvector extension is not available")
        print("PASS: isolated PostgreSQL + pgvector schema smoke test")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
