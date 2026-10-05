from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.schemas.workflow import (
    NaturalWorkflowRequest,
    NaturalWorkflowResponse,
    WorkflowPlan,
)
from app.services.natural_language_workflow import NaturalLanguageWorkflowService

router = APIRouter(prefix="/assistant", tags=["assistant-workflow"])
service = NaturalLanguageWorkflowService()


@router.post("/preview", response_model=WorkflowPlan)
async def preview(payload: NaturalWorkflowRequest):
    return service.preview(payload)


@router.post("", response_model=NaturalWorkflowResponse)
async def run(
    payload: NaturalWorkflowRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.run(session, payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
