import re
import secrets
import uuid

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import get_settings
from app.models.entities import Source
from app.services.embeddings import EmbeddingError, EmbeddingService
from app.services.source_ingestion import SourceIngestionError, SourceIngestionService

router = APIRouter(prefix="/admin/library", tags=["admin-library"])
settings = get_settings()
ingestion = SourceIngestionService()
embeddings = EmbeddingService()


def _admin(key: str | None):
    if not settings.admin_api_key:
        raise HTTPException(status_code=503, detail="ADMIN_API_KEY is not configured")
    if not key or not secrets.compare_digest(key, settings.admin_api_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")


def _key(title: str, grade: int | None, subject: str | None) -> str:
    slug = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ]+", "_", title).strip("_")[:60]
    return f"USR_{subject or 'GEN'}_{grade or 'NA'}_{slug}_{uuid.uuid4().hex[:8]}"


@router.post("/books")
async def add_book(
    file: UploadFile = File(...),
    title: str = Form(...),
    subject: str | None = Form(default=None),
    grade: int | None = Form(default=None),
    level: str | None = Form(default="basic"),
    author: str | None = Form(default=None),
    year: int | None = Form(default=None),
    publisher: str | None = Form(default=None),
    status: str = Form(default="secondary"),
    source_key: str | None = Form(default=None),
    auto_embed: bool = Form(default=True),
    x_admin_key: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    _admin(x_admin_key)
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Only PDF is supported")

    key = source_key or _key(title, grade, subject)
    existing = await session.scalar(select(Source).where(Source.source_key == key))
    if existing:
        raise HTTPException(status_code=409, detail=f"source_key already exists: {key}")

    source = Source(
        source_key=key,
        title=title,
        author=author,
        subject=subject,
        grade=grade,
        level=level,
        year=year,
        publisher=publisher,
        source_type="textbook",
        status=status,
        origin="admin_upload",
        access_status="authorized",
        authority_rank=90 if status == "primary" else 75,
        verification_status="uploaded_unreviewed",
        rollout_status="pilot",
        availability_status="file_pending",
        ingestion_status="file_pending",
        is_current=True,
        metadata_json={"added_via": "admin_library_v1_4"},
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)

    try:
        ingested = await ingestion.ingest_pdf(session, source.id, file, replace=False)
    except SourceIngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    embed_result = None
    if auto_embed and not ingested.get("needs_ocr"):
        try:
            embed_result = await embeddings.embed_source(session, source.id)
        except EmbeddingError as exc:
            embed_result = {"warning": str(exc)}

    return {
        "source_id": str(source.id),
        "source_key": source.source_key,
        "title": source.title,
        "ingestion": ingested,
        "embedding": embed_result,
        "bot_restart_required": False,
        "note": (
            "Книга добавлена в live library. Перезапуск Telegram-бота не нужен. "
            "Новая книга участвует в последующих запросах сразу после успешной индексации."
        ),
    }
