from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.schemas.pedagogy import PedagogyGenerationRequest, PedagogyGenerationResponse
from app.services.curriculum_resolver import CurriculumResolutionError
from app.services.pedagogy_generation import PedagogyGenerationError, PedagogyGenerationService
from app.services.retrieval import RetrievalError

router = APIRouter(prefix="/pedagogy", tags=["pedagogy"])
service = PedagogyGenerationService()


@router.post("/generate", response_model=PedagogyGenerationResponse)
async def generate_artifact(payload: PedagogyGenerationRequest, session: AsyncSession = Depends(get_session)):
    try:
        return await service.generate(session, payload)
    except CurriculumResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RetrievalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PedagogyGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
