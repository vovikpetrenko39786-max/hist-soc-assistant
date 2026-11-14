"""Exercise database and file backup restoration using disposable CI data only.

This script deliberately accepts one exact localhost database URL. It must never be
repurposed for production backup work: the goal is to prove the restore mechanism in
CI without reading or mutating Railway, production storage, or real user data.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
import uuid

import psycopg
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from ci_db_schema_smoke import validated_ci_database_url


CI_DATABASE_DSN = "postgresql://ci@127.0.0.1:5432/hist_soc_ci"
MAINTENANCE_DSN = "postgresql://ci@127.0.0.1:5432/postgres"
RESTORE_DATABASE_NAME = "hist_soc_ci_restore"
RESTORE_DATABASE_URL = (
    "postgresql+asyncpg://ci:ci_test@127.0.0.1:5432/" + RESTORE_DATABASE_NAME
)
SENTINEL_NAME = "CI restore drill sentinel"


def command_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PGPASSWORD"] = "ci_test"
    return environment


def require_postgres_tools() -> tuple[str, str]:
    pg_dump = shutil.which("pg_dump")
    pg_restore = shutil.which("pg_restore")
    if not pg_dump or not pg_restore:
        raise RuntimeError("pg_dump and pg_restore must be available on the CI runner")
    return pg_dump, pg_restore


def recreate_restore_database() -> None:
    with psycopg.connect(MAINTENANCE_DSN, password="ci_test", autocommit=True) as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(RESTORE_DATABASE_NAME)
            )
        )
        connection.execute(
            sql.SQL("CREATE DATABASE {} OWNER ci").format(
                sql.Identifier(RESTORE_DATABASE_NAME)
            )
        )


def drop_restore_database() -> None:
    with psycopg.connect(MAINTENANCE_DSN, password="ci_test", autocommit=True) as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(RESTORE_DATABASE_NAME)
            )
        )


def run_backup_restore(pg_dump: str, pg_restore: str, backup_path: Path) -> None:
    environment = command_environment()
    subprocess.run(
        [
            pg_dump,
            "--dbname",
            CI_DATABASE_DSN,
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--file",
            str(backup_path),
        ],
        check=True,
        env=environment,
    )
    if not backup_path.is_file() or backup_path.stat().st_size == 0:
        raise RuntimeError("pg_dump did not create a non-empty backup")

    recreate_restore_database()
    subprocess.run(
        [
            pg_restore,
            "--dbname",
            f"postgresql://ci@127.0.0.1:5432/{RESTORE_DATABASE_NAME}",
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            str(backup_path),
        ],
        check=True,
        env=environment,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_manifest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def validate_archive_members(archive: tarfile.TarFile) -> None:
    for member in archive.getmembers():
        member_path = PurePosixPath(member.name)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise RuntimeError(f"Unsafe archive path: {member.name}")
        if member.issym() or member.islnk():
            raise RuntimeError(f"Archive links are not allowed: {member.name}")


def exercise_file_restore(workspace: Path) -> None:
    source = workspace / "source_files"
    source.mkdir()
    (source / "lesson-plan.docx").write_bytes(b"synthetic DOCX fixture\x00\x01")
    textbook = source / "textbooks" / "history"
    textbook.mkdir(parents=True)
    (textbook / "chapter-01.txt").write_text(
        "Synthetic CI textbook content. No production data.\n", encoding="utf-8"
    )
    expected = file_manifest(source)

    archive_path = workspace / "files-backup.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source, arcname="payload", recursive=True)

    restored_root = workspace / "restored_files"
    restored_root.mkdir()
    with tarfile.open(archive_path, "r:gz") as archive:
        validate_archive_members(archive)
        archive.extractall(restored_root, filter="data")

    restored = restored_root / "payload"
    actual = file_manifest(restored)
    if actual != expected:
        raise RuntimeError("Restored file manifest does not match the backup source")


async def insert_sentinel(database_url: str, sentinel_id: uuid.UUID) -> None:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO teachers (
                        id, display_name, school_name, default_lesson_duration,
                        timezone, preferences, created_at, updated_at
                    ) VALUES (
                        CAST(:teacher_id AS UUID), :display_name, NULL, 45,
                        'UTC', CAST(:preferences AS JSONB), NOW(), NOW()
                    )
                    """
                ),
                {
                    "teacher_id": str(sentinel_id),
                    "display_name": SENTINEL_NAME,
                    "preferences": '{"fixture":"ci_restore_drill"}',
                },
            )
    finally:
        await engine.dispose()


async def delete_sentinel(database_url: str, sentinel_id: uuid.UUID) -> None:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM teachers WHERE id = CAST(:teacher_id AS UUID)"),
                {"teacher_id": str(sentinel_id)},
            )
    finally:
        await engine.dispose()


async def verify_restored_database(sentinel_id: uuid.UUID) -> None:
    engine = create_async_engine(RESTORE_DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            restored_name = await connection.scalar(
                text(
                    "SELECT display_name FROM teachers "
                    "WHERE id = CAST(:teacher_id AS UUID)"
                ),
                {"teacher_id": str(sentinel_id)},
            )
            if restored_name != SENTINEL_NAME:
                raise RuntimeError("Restored database is missing the synthetic sentinel")

            generation_runs = await connection.scalar(
                text("SELECT to_regclass('public.generation_runs') IS NOT NULL")
            )
            if not generation_runs:
                raise RuntimeError("Restored database is missing generation_runs")

            vector = await connection.scalar(
                text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            )
            if not vector:
                raise RuntimeError("Restored database is missing the pgvector extension")
    finally:
        await engine.dispose()


async def main() -> None:
    if os.getenv("APP_ENV") != "test":
        raise RuntimeError("CI restore drill requires APP_ENV=test")
    if any(os.getenv(name) for name in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID")):
        raise RuntimeError("Refusing to run the CI restore drill inside Railway")

    database_url = validated_ci_database_url(os.getenv("DATABASE_URL"))
    pg_dump, pg_restore = require_postgres_tools()
    sentinel_id = uuid.uuid4()
    sentinel_inserted = False
    try:
        await insert_sentinel(database_url, sentinel_id)
        sentinel_inserted = True
        with tempfile.TemporaryDirectory(prefix="hist-soc-restore-drill-") as temp_dir:
            workspace = Path(temp_dir)
            run_backup_restore(pg_dump, pg_restore, workspace / "database.dump")
            await verify_restored_database(sentinel_id)
            exercise_file_restore(workspace)
        print("PASS: isolated PostgreSQL + pgvector + file backup restore drill")
    finally:
        if sentinel_inserted:
            await delete_sentinel(database_url, sentinel_id)
        drop_restore_database()


if __name__ == "__main__":
    asyncio.run(main())
