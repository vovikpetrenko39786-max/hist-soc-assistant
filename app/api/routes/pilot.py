import secrets
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import get_settings
from app.models.entities import ExportedFile, GenerationRun, PilotFeedback
from app.schemas.pilot import PilotFeedbackCreate

router = APIRouter(prefix="/pilot", tags=["pilot"])
settings = get_settings()


def _require_admin(x_admin_key: str | None):
    if not settings.admin_api_key:
        raise HTTPException(status_code=503, detail="ADMIN_API_KEY is not configured")
    if not x_admin_key or not secrets.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")


@router.post("/feedback")
async def create_feedback(
    payload: PilotFeedbackCreate,
    session: AsyncSession = Depends(get_session),
):
    row = PilotFeedback(
        channel=payload.channel,
        category=payload.category,
        user_external_id=payload.user_external_id,
        username=payload.username,
        display_name=payload.display_name,
        text=payload.text,
        last_request=payload.last_request,
        generation_run_id=payload.generation_run_id,
        metadata_json=payload.metadata,
        status="new",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return {
        "id": str(row.id),
        "status": row.status,
        "message": "Спасибо. Отзыв сохранён для разбора пилота.",
    }


@router.get("/feedback")
async def list_feedback(
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = None,
    x_admin_key: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    _require_admin(x_admin_key)
    stmt = select(PilotFeedback).order_by(PilotFeedback.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(PilotFeedback.status == status)
    rows = list((await session.execute(stmt)).scalars().all())
    return [{
        "id": str(x.id),
        "category": x.category,
        "channel": x.channel,
        "user_external_id": x.user_external_id,
        "username": x.username,
        "display_name": x.display_name,
        "text": x.text,
        "last_request": x.last_request,
        "generation_run_id": str(x.generation_run_id) if x.generation_run_id else None,
        "metadata": x.metadata_json,
        "status": x.status,
        "created_at": x.created_at.isoformat(),
    } for x in rows]


@router.get("/stats")
async def pilot_stats(
    x_admin_key: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    _require_admin(x_admin_key)
    feedback_total = await session.scalar(select(func.count(PilotFeedback.id))) or 0
    feedback_open = await session.scalar(
        select(func.count(PilotFeedback.id)).where(PilotFeedback.status == "new")
    ) or 0
    generation_total = await session.scalar(select(func.count(GenerationRun.id))) or 0
    generation_failed = await session.scalar(
        select(func.count(GenerationRun.id)).where(GenerationRun.status == "quality_failed")
    ) or 0
    exports_total = await session.scalar(select(func.count(ExportedFile.id))) or 0
    return {
        "release": settings.pilot_release_label,
        "feedback_total": int(feedback_total),
        "feedback_open": int(feedback_open),
        "generation_total": int(generation_total),
        "generation_failed": int(generation_failed),
        "exports_total": int(exports_total),
    }


@router.get("/health")
async def pilot_health():
    return {
        "ok": True,
        "release": settings.pilot_release_label,
        "openai_configured": bool(settings.openai_api_key),
        "telegram_configured": bool(settings.telegram_bot_token),
        "generation_provider": settings.generation_provider,
        "generation_model": (
            settings.openai_generation_model
            if settings.generation_provider == "openai_responses"
            else settings.generation_model
        ),
    }
