"""PostgreSQL regression tests for atomic source replacement.

The suite is disabled unless an exact, disposable localhost URL is supplied.
It must never be pointed at Railway or any shared database.
"""
from __future__ import annotations

import io
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

import fitz
import pytest
import pytest_asyncio
from fastapi import UploadFile
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401 - register complete metadata
from app.db.base import Base
from app.models.entities import (
    Source,
    SourceChunk,
    SourceIngestionRun,
    SourcePage,
    SourceSection,
)
from app.services.source_ingestion import SourceIngestionError, SourceIngestionService


EXPECTED_URL = (
    "postgresql+asyncpg://ci:ci_test@127.0.0.1:55432/"
    "hist_soc_ingestion_test"
)


def validated_test_database_url() -> str | None:
    raw = os.getenv("INGESTION_TEST_DATABASE_URL")
    if not raw:
        return None
    url = make_url(raw)
    expected = make_url(EXPECTED_URL)
    if url != expected:
        raise RuntimeError(
            "Refusing source-ingestion integration test outside the exact "
            "disposable localhost database"
        )
    return raw


pytestmark = pytest.mark.skipif(
    not os.getenv("INGESTION_TEST_DATABASE_URL"),
    reason="requires the dedicated disposable localhost PostgreSQL database",
)


@pytest_asyncio.fixture
async def database():
    url = validated_test_database_url()
    if url is None:
        pytest.skip("integration database is not configured")

    admin_engine = create_async_engine(url, pool_pre_ping=True)
    schema = f"ingestion_{uuid.uuid4().hex}"
    async with admin_engine.begin() as connection:
        # The URL guard above makes this safe for the disposable local database only.
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_async_engine(
        url,
        pool_pre_ping=True,
        connect_args={"server_settings": {"search_path": f'"{schema}",public'}},
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin_engine.dispose()


def pdf_upload(name: str = "replacement.pdf") -> UploadFile:
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(
        (72, 72, 520, 760),
        "Учебный текст. " * 200,
        fontsize=10,
    )
    payload = document.tobytes()
    document.close()
    return UploadFile(filename=name, file=io.BytesIO(payload))


async def create_active_source(session, tmp_path: Path, suffix: str):
    old_path = tmp_path / f"old-{suffix}.pdf"
    old_path.write_bytes(b"old source bytes")
    source = Source(
        source_key=f"source-{suffix}",
        title="Existing source",
        source_type="textbook",
        status="current",
        file_path=str(old_path),
        file_hash=(suffix * 64)[:64],
        page_count=1,
        has_text_layer=True,
        text_char_count=8,
        availability_status="rag_ready",
        ingestion_status="rag_ready",
        metadata_json={"stable": True},
    )
    session.add(source)
    await session.flush()
    page = SourcePage(
        source_id=source.id,
        page_number_pdf=1,
        text="old page",
        text_hash="old-page",
        char_count=8,
        has_text=True,
        metadata_json={},
    )
    section = SourceSection(
        source_id=source.id,
        toc_level=1,
        title="Old section",
        start_page_pdf=1,
        end_page_pdf=1,
        order_index=0,
        metadata_json={},
    )
    session.add_all([page, section])
    await session.flush()
    chunk = SourceChunk(
        source_id=source.id,
        section_id=section.id,
        chunk_index=0,
        section="Old section",
        page_pdf=1,
        page_pdf_end=1,
        content_type="main_text",
        text="old chunk",
        text_hash="old-chunk",
        char_count=9,
        embedding_status="ready",
        metadata_json={},
    )
    session.add(chunk)
    await session.commit()
    return source, page.id, section.id, chunk.id


@pytest.mark.asyncio
async def test_failed_replacement_preserves_active_derivatives(database, tmp_path, monkeypatch):
    async with database() as session:
        source, page_id, section_id, chunk_id = await create_active_source(
            session, tmp_path, "a"
        )
        source_id = source.id
        original = {
            "file_path": source.file_path,
            "file_hash": source.file_hash,
            "availability_status": source.availability_status,
            "ingestion_status": source.ingestion_status,
            "page_count": source.page_count,
            "text_char_count": source.text_char_count,
            "metadata_json": source.metadata_json,
        }

    service = SourceIngestionService()
    service.settings = SimpleNamespace(source_storage_dir=str(tmp_path / "sources"))

    def fail_after_derivative_deletes(_inspection):
        raise RuntimeError("synthetic chunking failure")

    monkeypatch.setattr(service.analyzer, "make_chunks", fail_after_derivative_deletes)
    async with database() as session:
        with pytest.raises(SourceIngestionError, match="synthetic chunking failure"):
            await service.ingest_pdf(session, source_id, pdf_upload(), replace=True)

    async with database() as session:
        source = await session.get(Source, source_id)
        assert source is not None
        for field, expected in original.items():
            assert getattr(source, field) == expected
        assert set(await session.scalars(
            select(SourcePage.id).where(SourcePage.source_id == source_id)
        )) == {page_id}
        assert set(await session.scalars(
            select(SourceSection.id).where(SourceSection.source_id == source_id)
        )) == {section_id}
        assert set(await session.scalars(
            select(SourceChunk.id).where(SourceChunk.source_id == source_id)
        )) == {chunk_id}
        failed_run = await session.scalar(
            select(SourceIngestionRun)
            .where(SourceIngestionRun.source_id == source_id)
            .order_by(SourceIngestionRun.started_at.desc())
        )
        assert failed_run is not None
        assert failed_run.status == "failed"
        assert failed_run.file_hash != source.file_hash
        assert "synthetic chunking failure" in (failed_run.error_message or "")


@pytest.mark.asyncio
async def test_failed_first_ingest_marks_source_failed(database, tmp_path, monkeypatch):
    async with database() as session:
        source = Source(
            source_key="first-ingest",
            title="New source",
            source_type="textbook",
            status="current",
            availability_status="metadata_only",
            ingestion_status="file_pending",
            metadata_json={},
        )
        session.add(source)
        await session.commit()
        source_id = source.id

    service = SourceIngestionService()
    service.settings = SimpleNamespace(source_storage_dir=str(tmp_path / "sources"))
    monkeypatch.setattr(
        service.analyzer,
        "inspect",
        lambda _path: (_ for _ in ()).throw(RuntimeError("synthetic inspection failure")),
    )
    async with database() as session:
        with pytest.raises(SourceIngestionError, match="synthetic inspection failure"):
            await service.ingest_pdf(session, source_id, pdf_upload())

    async with database() as session:
        source = await session.get(Source, source_id)
        assert source is not None
        assert source.file_path is None
        assert source.file_hash is None
        assert source.ingestion_status == "failed"
        failed_run = await session.scalar(
            select(SourceIngestionRun).where(SourceIngestionRun.source_id == source_id)
        )
        assert failed_run is not None
        assert failed_run.status == "failed"


@pytest.mark.asyncio
async def test_successful_replacement_switches_all_derivatives(database, tmp_path):
    async with database() as session:
        source, page_id, section_id, chunk_id = await create_active_source(
            session, tmp_path, "b"
        )
        source_id = source.id
        old_hash = source.file_hash

    service = SourceIngestionService()
    service.settings = SimpleNamespace(source_storage_dir=str(tmp_path / "sources"))
    async with database() as session:
        result = await service.ingest_pdf(session, source_id, pdf_upload(), replace=True)
        assert result["status"] == "chunked_embedding_pending"

    async with database() as session:
        source = await session.get(Source, source_id)
        assert source is not None
        assert source.file_hash != old_hash
        assert not await session.get(SourcePage, page_id)
        assert not await session.get(SourceSection, section_id)
        assert not await session.get(SourceChunk, chunk_id)
        assert len(list(await session.scalars(
            select(SourcePage.id).where(SourcePage.source_id == source_id)
        ))) == source.page_count
        assert list(await session.scalars(
            select(SourceChunk.id).where(SourceChunk.source_id == source_id)
        ))
