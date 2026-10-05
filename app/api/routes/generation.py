from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.schemas.generation import GroundedLessonResponse, LessonGenerationRequest
from app.services.curriculum_resolver import CurriculumResolutionError
from app.services.grounded_generation import GroundedGenerationError, GroundedLessonService
from app.services.retrieval import RetrievalError

router = APIRouter(prefix="/generation", tags=["generation"])
service = GroundedLessonService()


@router.post("/lesson", response_model=GroundedLessonResponse)
async def generate_lesson(
    payload: LessonGenerationRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.generate(session, payload)
    except CurriculumResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RetrievalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GroundedGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
