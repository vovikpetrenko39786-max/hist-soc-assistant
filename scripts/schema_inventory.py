"""Produce a read-only PostgreSQL schema inventory without exposing credentials."""
from __future__ import annotations

import argparse
import asyncio
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def normalize_database_url(raw: str | None) -> str:
    if not raw or not raw.strip():
        raise ValueError("DATABASE_URL is required")
    value = raw.strip()
    if value.startswith("postgres://"):
        value = "postgresql+asyncpg://" + value[len("postgres://"):]
    elif value.startswith("postgresql://"):
        value = "postgresql+asyncpg://" + value[len("postgresql://"):]
    url = make_url(value)
    if url.drivername != "postgresql+asyncpg":
        raise ValueError("Only postgresql+asyncpg inventory targets are supported")
    return value


def inventory_fingerprint(payload: dict[str, Any]) -> str:
    # Environment identity is reported, but excluded so identical schemas in
    # differently named databases/PostgreSQL patch releases compare equally.
    comparable = {
        key: value
        for key, value in payload.items()
        if key not in {"database", "server_version", "schema_fingerprint"}
    }
    canonical = json.dumps(
        comparable,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


async def collect_inventory(database_url: str, schema: str = "public") -> dict[str, Any]:
    if not _SCHEMA_RE.fullmatch(schema):
        raise ValueError("Invalid schema name")
    url = normalize_database_url(database_url)
    engine = create_async_engine(url, pool_pre_ping=True, pool_size=1, max_overflow=0)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text("SET TRANSACTION READ ONLY"))
                await connection.execute(text("SET LOCAL statement_timeout = '15s'"))
                database = await connection.scalar(text("SELECT current_database()"))
                server_version = await connection.scalar(text("SHOW server_version"))
                extensions = list((await connection.execute(text("""
                    SELECT extname AS name, extversion AS version
                    FROM pg_extension
                    ORDER BY extname
                """))).mappings())
                tables = list((await connection.execute(text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = :schema AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """), {"schema": schema})).mappings())
                columns = list((await connection.execute(text("""
                    SELECT table_name, column_name, ordinal_position, data_type,
                           udt_name, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = :schema
                    ORDER BY table_name, ordinal_position
                """), {"schema": schema})).mappings())
                constraints = list((await connection.execute(text("""
                    SELECT cls.relname AS table_name, con.conname AS name,
                           con.contype AS type,
                           pg_get_constraintdef(con.oid, true) AS definition
                    FROM pg_constraint AS con
                    JOIN pg_class AS cls ON cls.oid = con.conrelid
                    JOIN pg_namespace AS ns ON ns.oid = cls.relnamespace
                    WHERE ns.nspname = :schema
                    ORDER BY cls.relname, con.conname
                """), {"schema": schema})).mappings())
                indexes = list((await connection.execute(text("""
                    SELECT tablename AS table_name, indexname AS name,
                           indexdef AS definition
                    FROM pg_indexes
                    WHERE schemaname = :schema
                    ORDER BY tablename, indexname
                """), {"schema": schema})).mappings())
                version_table = await connection.scalar(
                    text("SELECT to_regclass(:table_name) IS NOT NULL"),
                    {"table_name": f"{schema}.alembic_version"},
                )
                alembic_versions: list[str] = []
                if version_table:
                    result = await connection.execute(
                        text(f'SELECT version_num FROM "{schema}".alembic_version '
                             "ORDER BY version_num")
                    )
                    alembic_versions = list(result.scalars())
    finally:
        await engine.dispose()

    payload: dict[str, Any] = {
        "database": database,
        "schema": schema,
        "server_version": server_version,
        "extensions": [dict(row) for row in extensions],
        "tables": [dict(row) for row in tables],
        "columns": [dict(row) for row in columns],
        "constraints": [dict(row) for row in constraints],
        "indexes": [dict(row) for row in indexes],
        "alembic_versions": alembic_versions,
    }
    payload["schema_fingerprint"] = inventory_fingerprint(payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--schema", default="public")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        payload = asyncio.run(collect_inventory(args.database_url, args.schema))
    except Exception as exc:
        raise SystemExit(f"Schema inventory failed: {type(exc).__name__}") from exc
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
