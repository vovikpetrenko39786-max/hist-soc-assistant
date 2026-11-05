import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.pilot_auth import authorize_course, require_user_principal
from app.schemas.workflow import (
    NaturalWorkflowRequest,
    NaturalWorkflowResponse,
    WorkflowPlan,
)
from app.services.natural_language_workflow import NaturalLanguageWorkflowService

router = APIRouter(prefix="/assistant", tags=["assistant-workflow"])
service = NaturalLanguageWorkflowService()
logger = logging.getLogger(__name__)


@router.post("/preview", response_model=WorkflowPlan)
async def preview(payload: NaturalWorkflowRequest):
    return service.preview(payload)


@router.post("", response_model=NaturalWorkflowResponse)
async def run(
    payload: NaturalWorkflowRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    try:
        principal = require_user_principal(request)
        if payload.class_course_id:
            authorize_course(request, payload.class_course_id)
        return await service.run(
            session,
            payload,
            owner_principal=(
                f"telegram:{principal.external_id}" if principal.external_id else "admin"
            ),
        )
    except Exception as exc:
        logger.exception("Assistant workflow failed")
        raise HTTPException(status_code=500, detail="Internal generation error") from exc
