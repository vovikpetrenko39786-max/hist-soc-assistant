import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.models.entities import Lesson, LessonStatus
from app.schemas.lessons import LessonComplete, LessonCreate

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.post("")
async def create_lesson(
    payload: LessonCreate,
    session: AsyncSession = Depends(get_session),
):
    lesson = Lesson(
        class_course_id=payload.class_course_id,
        date=payload.date,
        lesson_number=payload.lesson_number,
        topic=payload.topic,
        lesson_type=payload.lesson_type,
        duration_minutes=payload.duration_minutes,
        planned_content=payload.planned_content,
        status=LessonStatus.planned,
    )
    session.add(lesson)
    await session.commit()
    await session.refresh(lesson)
    return {"id": str(lesson.id), "status": lesson.status.value}


@router.post("/{lesson_id}/complete")
async def complete_lesson(
    lesson_id: uuid.UUID,
    payload: LessonComplete,
    session: AsyncSession = Depends(get_session),
):
    row = await session.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = row.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    lesson.completed_content = payload.completed_content
    lesson.unfinished_content = payload.unfinished_content
    lesson.reflection = payload.reflection
    lesson.next_step = payload.next_step
    lesson.status = (
        LessonStatus.partially_completed if payload.partial else LessonStatus.completed
    )
    await session.commit()
    return {"id": str(lesson.id), "status": lesson.status.value}
