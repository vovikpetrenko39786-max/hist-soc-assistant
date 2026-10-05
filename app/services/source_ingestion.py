from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re
import shutil
import uuid

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import (
    Source,
    SourceChunk,
    SourceIngestionRun,
    SourcePage,
    SourceSection,
)
from app.services.pdf_ingestion import PDFIngestionAnalyzer


class SourceIngestionError(Exception):
    pass


class DuplicateSourceFileError(SourceIngestionError):
    def __init__(self, source_id: uuid.UUID):
        super().__init__(f'Identical file is already attached to source {source_id}')
        self.source_id = source_id


class SourceIngestionService:
    def __init__(self):
        self.settings = get_settings()
        self.analyzer = PDFIngestionAnalyzer()

    def _storage_root(self) -> Path:
        base = Path(self.settings.source_storage_dir)
        if not base.is_absolute():
            project_root = Path(__file__).resolve().parents[2]
            base = project_root / base
        base.mkdir(parents=True, exist_ok=True)
        return base

    @staticmethod
    def _safe_filename(filename: str) -> str:
        filename = Path(filename).name
        stem = re.sub(r'[^0-9A-Za-zА-Яа-я._-]+', '_', filename).strip('._')
        return stem or 'source.pdf'

    async def _save_upload(self, upload: UploadFile, temp_path: Path) -> tuple[str, int]:
        h = sha256()
        total = 0
        with temp_path.open('wb') as out:
            while True:
                block = await upload.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                h.update(block)
                out.write(block)
        await upload.seek(0)
        return h.hexdigest(), total

    async def ingest_pdf(
        self,
        session: AsyncSession,
        source_id: uuid.UUID,
        upload: UploadFile,
        replace: bool = False,
    ) -> dict:
        source = await session.scalar(select(Source).where(Source.id == source_id))
        if source is None:
            raise SourceIngestionError('Source not found')

        original_name = upload.filename or 'source.pdf'
        if Path(original_name).suffix.lower() != '.pdf':
            raise SourceIngestionError('Only PDF uploads are accepted in v0.7')

        storage_root = self._storage_root()
        source_dir = storage_root / str(source.id)
        source_dir.mkdir(parents=True, exist_ok=True)
        temp_path = source_dir / '.upload.tmp'
        file_hash, size_bytes = await self._save_upload(upload, temp_path)

        duplicate = await session.scalar(
            select(Source).where(Source.file_hash == file_hash, Source.id != source.id)
        )
        if duplicate is not None:
            temp_path.unlink(missing_ok=True)
            raise DuplicateSourceFileError(duplicate.id)

        if source.file_hash and source.file_hash != file_hash and not replace:
            temp_path.unlink(missing_ok=True)
            raise SourceIngestionError('Source already has another file. Use replace=true to replace it.')

        final_name = f'{file_hash[:12]}_{self._safe_filename(original_name)}'
        final_path = source_dir / final_name
        temp_path.replace(final_path)

        run = SourceIngestionRun(
            source_id=source.id,
            status='file_received',
            original_filename=original_name,
            stored_file_path=str(final_path),
            file_hash=file_hash,
            file_size_bytes=size_bytes,
            extraction_method='pymupdf',
        )
        session.add(run)
        await session.flush()

        try:
            inspection = self.analyzer.inspect(final_path)
            run.status = 'validated'
            run.page_count = inspection.page_count
            run.text_char_count = inspection.text_char_count
            run.pages_with_text = inspection.pages_with_text
            run.needs_ocr = inspection.needs_ocr

            if inspection.page_count == 0:
                raise SourceIngestionError('PDF has no pages')

            # Re-ingestion is replacement of extracted derivatives for this source.
            await session.execute(delete(SourceChunk).where(SourceChunk.source_id == source.id))
            await session.execute(delete(SourceSection).where(SourceSection.source_id == source.id))
            await session.execute(delete(SourcePage).where(SourcePage.source_id == source.id))

            for page in inspection.pages:
                session.add(SourcePage(
                    source_id=source.id,
                    page_number_pdf=page.page_number_pdf,
                    page_label=page.page_label,
                    printed_page=page.printed_page,
                    text=page.text,
                    text_hash=page.text_hash,
                    char_count=page.char_count,
                    has_text=page.has_text,
                    extraction_method='pymupdf',
                    metadata_json={'width': page.width, 'height': page.height},
                ))
            run.status = 'text_extracted'
            await session.flush()

            section_rows: dict[int, SourceSection] = {}
            for sec in inspection.sections:
                parent = section_rows.get(sec.parent_order_index) if sec.parent_order_index is not None else None
                row = SourceSection(
                    source_id=source.id,
                    parent_section_id=parent.id if parent else None,
                    toc_level=sec.level,
                    title=sec.title,
                    start_page_pdf=sec.start_page_pdf,
                    end_page_pdf=sec.end_page_pdf,
                    order_index=sec.order_index,
                )
                session.add(row)
                await session.flush()
                section_rows[sec.order_index] = row
            run.sections_created = len(section_rows)

            chunks = self.analyzer.make_chunks(inspection)
            for chunk in chunks:
                sec_row = section_rows.get(chunk.section_order_index) if chunk.section_order_index is not None else None
                session.add(SourceChunk(
                    source_id=source.id,
                    section_id=sec_row.id if sec_row else None,
                    chunk_index=chunk.chunk_index,
                    section=sec_row.title[:300] if sec_row else None,
                    page_pdf=chunk.page_pdf_start,
                    page_pdf_end=chunk.page_pdf_end,
                    page_print=chunk.page_print_start,
                    page_print_end=chunk.page_print_end,
                    content_type='main_text',
                    text=chunk.text,
                    text_hash=chunk.text_hash,
                    char_count=chunk.char_count,
                    embedding_status='pending',
                    metadata_json={'ingestion_version': 'v0.7'},
                ))
            run.chunks_created = len(chunks)

            source.file_path = str(final_path)
            source.file_hash = inspection.file_hash
            source.page_count = inspection.page_count
            source.has_text_layer = inspection.has_text_layer
            source.text_char_count = inspection.text_char_count
            source.ingested_at = datetime.now(timezone.utc)
            source.metadata_json = {
                **(source.metadata_json or {}),
                'pdf_metadata': inspection.metadata,
                'pages_with_text': inspection.pages_with_text,
                'ingestion_version': 'v0.7',
            }

            if inspection.needs_ocr:
                source.availability_status = 'needs_ocr'
                source.ingestion_status = 'needs_ocr'
                run.status = 'needs_ocr'
            elif chunks:
                # Chunks exist, but embeddings are intentionally not generated in v0.7.
                source.availability_status = 'chunked'
                source.ingestion_status = 'chunked_embedding_pending'
                run.status = 'chunked_embedding_pending'
            else:
                source.availability_status = 'text_extracted'
                source.ingestion_status = 'text_extracted'
                run.status = 'text_extracted'

            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(run)

            return self._run_result(source, run)
        except Exception as exc:
            run.status = 'failed'
            run.error_message = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            source.ingestion_status = 'failed'
            await session.commit()
            if isinstance(exc, SourceIngestionError):
                raise
            raise SourceIngestionError(str(exc)) from exc

    async def status(self, session: AsyncSession, source_id: uuid.UUID) -> dict:
        source = await session.scalar(select(Source).where(Source.id == source_id))
        if source is None:
            raise SourceIngestionError('Source not found')
        run = await session.scalar(
            select(SourceIngestionRun)
            .where(SourceIngestionRun.source_id == source_id)
            .order_by(SourceIngestionRun.started_at.desc())
            .limit(1)
        )
        return {
            'source_id': str(source.id),
            'source_key': source.source_key,
            'title': source.title,
            'availability_status': source.availability_status,
            'ingestion_status': source.ingestion_status,
            'file_path': source.file_path,
            'file_hash': source.file_hash,
            'page_count': source.page_count,
            'has_text_layer': source.has_text_layer,
            'text_char_count': source.text_char_count,
            'latest_run': None if run is None else self._run_only(run),
        }

    @staticmethod
    def _run_only(run: SourceIngestionRun) -> dict:
        return {
            'run_id': str(run.id),
            'status': run.status,
            'original_filename': run.original_filename,
            'file_hash': run.file_hash,
            'file_size_bytes': run.file_size_bytes,
            'page_count': run.page_count,
            'text_char_count': run.text_char_count,
            'pages_with_text': run.pages_with_text,
            'sections_created': run.sections_created,
            'chunks_created': run.chunks_created,
            'needs_ocr': run.needs_ocr,
            'error_message': run.error_message,
            'started_at': run.started_at.isoformat() if run.started_at else None,
            'completed_at': run.completed_at.isoformat() if run.completed_at else None,
        }

    def _run_result(self, source: Source, run: SourceIngestionRun) -> dict:
        return {
            'source_id': str(source.id),
            'source_key': source.source_key,
            'title': source.title,
            'availability_status': source.availability_status,
            'ingestion_status': source.ingestion_status,
            'file_hash': source.file_hash,
            'page_count': source.page_count,
            'has_text_layer': source.has_text_layer,
            'text_char_count': source.text_char_count,
            **self._run_only(run),
        }
