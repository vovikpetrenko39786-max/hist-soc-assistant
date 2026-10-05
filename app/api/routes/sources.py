import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_session
from app.schemas.sources import SourceCatalogOut, SourceIngestionOut, SourceIngestionStatusOut, SourceResolveRequest, SourceResolveResult
from app.services.sources import SourceCatalogService
from app.services.source_ingestion import DuplicateSourceFileError, SourceIngestionError, SourceIngestionService
from app.models.entities import SourcePage
from sqlalchemy import select

router=APIRouter(prefix='/sources',tags=['sources'])
service=SourceCatalogService()
ingestion_service=SourceIngestionService()

@router.get('', response_model=list[SourceCatalogOut])
async def list_sources(subject: str|None=None, grade: int|None=Query(default=None,ge=1,le=11), level: str|None=None, status: str|None=None, session: AsyncSession=Depends(get_session)):
    return await service.list_sources(session,subject,grade,level,status)

@router.post('/resolve-preview', response_model=list[SourceResolveResult])
async def resolve_preview(payload: SourceResolveRequest):
    return service.resolve_preview(payload.subject,payload.grade,payload.level,payload.unit_title,payload.topic_title)


@router.post('/{source_id}/ingest', response_model=SourceIngestionOut)
async def ingest_source_pdf(
    source_id: uuid.UUID,
    file: UploadFile = File(...),
    replace: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await ingestion_service.ingest_pdf(session, source_id, file, replace=replace)
    except DuplicateSourceFileError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                'message': str(exc),
                'existing_source_id': str(exc.source_id),
            },
        ) from exc
    except SourceIngestionError as exc:
        status_code = 404 if str(exc) == 'Source not found' else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get('/{source_id}/ingestion-status', response_model=SourceIngestionStatusOut)
async def source_ingestion_status(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await ingestion_service.status(session, source_id)
    except SourceIngestionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get('/{source_id}/pages/{page_number_pdf}')
async def get_source_page(
    source_id: uuid.UUID,
    page_number_pdf: int,
    session: AsyncSession = Depends(get_session),
):
    if page_number_pdf < 1:
        raise HTTPException(status_code=400, detail='page_number_pdf must be >= 1')
    page = await session.scalar(
        select(SourcePage).where(
            SourcePage.source_id == source_id,
            SourcePage.page_number_pdf == page_number_pdf,
        )
    )
    if page is None:
        raise HTTPException(status_code=404, detail='Source page not found')
    return {
        'source_id': str(source_id),
        'page_number_pdf': page.page_number_pdf,
        'page_label': page.page_label,
        'printed_page': page.printed_page,
        'text': page.text,
        'text_hash': page.text_hash,
        'char_count': page.char_count,
        'has_text': page.has_text,
        'extraction_method': page.extraction_method,
    }
