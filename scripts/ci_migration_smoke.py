"""Exercise Alembic only against an exact disposable localhost database."""
from __future__ import annotations

import asyncio
import os

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401 - register every ORM table
from app.db.base import Base


EXPECTED_URL = (
    "postgresql+asyncpg://ci:ci_test@127.0.0.1:55433/"
    "hist_soc_migration_test"
)
EXPECTED_REVISION = "0001"
EXPECTED_TABLE_COUNT = 36


def validated_test_database_url(raw: str | None) -> str:
    if not raw or make_url(raw) != make_url(EXPECTED_URL):
        raise RuntimeError(
            "Refusing migration smoke test outside the exact disposable localhost database"
        )
    return raw


def alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


async def assert_head_schema(database_url: str) -> None:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            tables = set((await connection.execute(text("""
                SELECT tablename FROM pg_tables WHERE schemaname = 'public'
            """))).scalars())
            expected = set(Base.metadata.tables)
            missing = expected - tables
            unexpected = tables - expected - {"alembic_version"}
            if missing or unexpected or len(expected) != EXPECTED_TABLE_COUNT:
                raise RuntimeError(
                    f"Schema mismatch: missing={sorted(missing)}, "
                    f"unexpected={sorted(unexpected)}, expected_count={len(expected)}"
                )
            revision = await connection.scalar(text(
                "SELECT version_num FROM alembic_version"
            ))
            if revision != EXPECTED_REVISION:
                raise RuntimeError(f"Unexpected Alembic revision: {revision}")
            vector = await connection.scalar(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'vector'
                )
            """))
            if not vector:
                raise RuntimeError("pgvector extension is missing")
            embedding_type = await connection.scalar(text("""
                SELECT format_type(attribute.atttypid, attribute.atttypmod)
                FROM pg_attribute AS attribute
                JOIN pg_class AS relation ON relation.oid = attribute.attrelid
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname = 'public'
                  AND relation.relname = 'source_chunks'
                  AND attribute.attname = 'embedding'
            """))
            if embedding_type != "vector":
                raise RuntimeError(f"Unexpected embedding column type: {embedding_type}")
    finally:
        await engine.dispose()


async def assert_base_schema(database_url: str) -> None:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            remaining = set((await connection.execute(text("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public' AND tablename <> 'alembic_version'
            """))).scalars())
            enums = int(await connection.scalar(text("""
                SELECT count(*) FROM pg_type AS type
                JOIN pg_namespace AS namespace ON namespace.oid = type.typnamespace
                WHERE namespace.nspname = 'public' AND type.typtype = 'e'
            """)) or 0)
            if remaining or enums:
                raise RuntimeError(
                    f"Downgrade left objects: tables={sorted(remaining)}, enums={enums}"
                )
    finally:
        await engine.dispose()


async def create_guard_sentinel(database_url: str) -> None:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(
                "CREATE TABLE migration_guard_sentinel (id integer PRIMARY KEY)"
            ))
    finally:
        await engine.dispose()


async def assert_guard_and_remove_sentinel(database_url: str) -> None:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            remaining = set((await connection.execute(text("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public' AND tablename <> 'alembic_version'
            """))).scalars())
            if remaining != {"migration_guard_sentinel"}:
                raise RuntimeError(
                    f"Empty-database guard allowed schema changes: {sorted(remaining)}"
                )
            await connection.execute(text("DROP TABLE migration_guard_sentinel"))
    finally:
        await engine.dispose()


def main() -> None:
    database_url = validated_test_database_url(
        os.getenv("MIGRATION_TEST_DATABASE_URL")
    )
    config = alembic_config(database_url)

    command.upgrade(config, "head")
    asyncio.run(assert_head_schema(database_url))
    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, "base")
    asyncio.run(assert_base_schema(database_url))
    asyncio.run(create_guard_sentinel(database_url))
    try:
        command.upgrade(config, "head")
    except Exception as exc:
        if "restricted to an empty PostgreSQL database" not in str(exc):
            raise
    else:
        raise RuntimeError("Revision 0001 accepted a non-empty database")
    asyncio.run(assert_guard_and_remove_sentinel(database_url))
    command.upgrade(config, "head")
    asyncio.run(assert_head_schema(database_url))
    command.check(config)
    print("PASS: isolated Alembic upgrade/check/downgrade/upgrade smoke test")


if __name__ == "__main__":
    main()
