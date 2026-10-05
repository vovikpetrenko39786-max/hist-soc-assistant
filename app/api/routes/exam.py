import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.schemas.exam import CodifierElementOut, ExamModelOut, ExamTaskOut, TopicExamMappingOut
from app.services.exam import ExamCatalogService

router = APIRouter(prefix="/exams", tags=["exams"])
service = ExamCatalogService()


@router.get("/models", response_model=list[ExamModelOut])
async def list_models(
    exam: str | None = Query(default=None),
    subject: str | None = Query(default=None),
    year: int | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    return await service.list_models(session, exam=exam, subject=subject, year=year)


@router.get("/models/{model_key}", response_model=ExamModelOut)
async def get_model(model_key: str, session: AsyncSession = Depends(get_session)):
    row = await service.get_model(session, model_key)
    if row is None:
        raise HTTPException(status_code=404, detail="Exam model not found")
    return row


@router.get("/models/{model_key}/tasks", response_model=list[ExamTaskOut])
async def get_tasks(model_key: str, session: AsyncSession = Depends(get_session)):
    return await service.get_tasks(session, model_key)


@router.get("/models/{model_key}/codifier", response_model=list[CodifierElementOut])
async def get_codifier(model_key: str, session: AsyncSession = Depends(get_session)):
    return await service.get_codifier(session, model_key)


@router.get("/topics/{topic_id}/mappings", response_model=list[TopicExamMappingOut])
async def topic_mappings(topic_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    rows = await service.get_topic_mappings(session, topic_id)
    return [
        TopicExamMappingOut(
            exam_model_key=x.exam_model.model_key,
            codifier_code=x.codifier_element.code if x.codifier_element else None,
            task_keys=x.task_keys or [],
            mapping_status=x.mapping_status,
            confidence=x.confidence,
            evidence_type=x.evidence_type,
            evidence_reference=x.evidence_reference,
            notes=x.notes,
        )
        for x in rows
    ]
