from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.schemas.web_knowledge import WebKnowledgeRequest, WebKnowledgeResponse
from app.services.web_knowledge import OfficialDomainPolicy, WebKnowledgeService

router = APIRouter(prefix="/web", tags=["web-knowledge"])
service = WebKnowledgeService()


@router.post("/search", response_model=WebKnowledgeResponse)
async def web_search(
    payload: WebKnowledgeRequest,
    session: AsyncSession = Depends(get_session),
):
    if payload.policy == "library_only":
        return {
            "performed": False,
            "provider": "openai",
            "model": None,
            "policy": payload.policy,
            "scope": payload.scope,
            "query": payload.query,
            "allowed_domains": [],
            "answer": None,
            "sources": [],
            "citations": [],
            "search_run_id": None,
            "warnings": ["library_only policy forbids external web search."],
        }
    return await service.search(
        session,
        query=payload.query,
        policy=payload.policy,
        subject=payload.subject,
        scope=payload.scope,
        force_search=payload.force_search,
        save_run=True,
    )


@router.get("/official-domains")
async def official_domains(query: str, subject: str | None = None):
    return {
        "query": query,
        "subject": subject,
        "allowed_domains": OfficialDomainPolicy.allowed_domains(query, subject),
    }
