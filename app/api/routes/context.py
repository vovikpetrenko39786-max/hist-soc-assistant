import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.services.memory import MemoryService

router = APIRouter(prefix="/class-courses", tags=["context"])
service = MemoryService()


@router.get("/{class_course_id}/context")
async def get_context(
    class_course_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    return await service.build_class_course_context(session, class_course_id)
