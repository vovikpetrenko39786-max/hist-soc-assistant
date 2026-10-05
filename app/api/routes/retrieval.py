import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.schemas.retrieval import RetrievalRequest, RetrievalResponse, SourceEmbeddingOut
from app.services.embeddings import EmbeddingError, EmbeddingService
from app.services.retrieval import RetrievalError, RetrievalService

router = APIRouter(prefix="/retrieval", tags=["retrieval"])
retrieval_service = RetrievalService()
embedding_service = EmbeddingService()


@router.post("/search", response_model=RetrievalResponse)
async def search(payload: RetrievalRequest, session: AsyncSession = Depends(get_session)):
    try:
        return await retrieval_service.retrieve(session, payload)
    except RetrievalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sources/{source_id}/embed", response_model=SourceEmbeddingOut)
async def embed_source(
    source_id: uuid.UUID,
    force: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await embedding_service.embed_source(session, source_id, force=force)
    except EmbeddingError as exc:
        status = 404 if str(exc) == "Source not found" else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
