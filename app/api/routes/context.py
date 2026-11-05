import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.pilot_auth import authorize_course
from app.services.memory import MemoryService

router = APIRouter(prefix="/class-courses", tags=["context"])
service = MemoryService()


@router.get("/{class_course_id}/context")
async def get_context(
    class_course_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    authorize_course(request, class_course_id)
    context = await service.build_class_course_context(session, class_course_id)
    context.pop("teacher_id", None)
    return context
