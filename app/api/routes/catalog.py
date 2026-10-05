import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_session
from app.schemas.catalog import CurriculumOut, SubjectOut, TopicCardOut, TopicSearchResult
from app.services.catalog import CurriculumCatalogService
router=APIRouter(prefix='/catalog', tags=['catalog']); service=CurriculumCatalogService()
@router.get('/subjects', response_model=list[SubjectOut])
async def subjects(session: AsyncSession=Depends(get_session)): return await service.list_subjects(session)
@router.get('/curricula', response_model=list[CurriculumOut])
async def curricula(subject:str|None=None, grade:int|None=Query(None,ge=1,le=11), level:str|None=None, session:AsyncSession=Depends(get_session)): return await service.list_curricula(session,subject,grade,level)
@router.get('/topics/search', response_model=list[TopicSearchResult])
async def topic_search(q:str|None=None, subject:str|None=None, grade:int|None=Query(None,ge=1,le=11), level:str|None=None, limit:int=Query(20,ge=1,le=100), session:AsyncSession=Depends(get_session)): return await service.search_topics(session,q,subject,grade,level,limit)
@router.get('/topics/{topic_id}', response_model=TopicCardOut)
async def topic_card(topic_id:uuid.UUID, session:AsyncSession=Depends(get_session)):
    card=await service.get_topic_card(session,topic_id)
    if card is None: raise HTTPException(404,'Topic not found')
    return card
