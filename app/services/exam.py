import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.exam import CodifierElement, ExamModel, ExamTask, TopicExamMapping


class ExamCatalogService:
    async def list_models(self, session: AsyncSession, exam: str | None = None, subject: str | None = None, year: int | None = None):
        stmt = select(ExamModel)
        if exam:
            stmt = stmt.where(ExamModel.exam == exam.upper())
        if subject:
            stmt = stmt.where(ExamModel.subject == subject)
        if year:
            stmt = stmt.where(ExamModel.year == year)
        rows = await session.execute(stmt.order_by(ExamModel.year.desc(), ExamModel.exam, ExamModel.subject))
        return rows.scalars().all()

    async def get_model(self, session: AsyncSession, model_key: str):
        row = await session.execute(select(ExamModel).where(ExamModel.model_key == model_key))
        return row.scalar_one_or_none()

    async def get_tasks(self, session: AsyncSession, model_key: str):
        stmt = select(ExamTask).join(ExamModel).where(ExamModel.model_key == model_key).order_by(ExamTask.task_number, ExamTask.task_key)
        rows = await session.execute(stmt)
        return rows.scalars().all()

    async def get_codifier(self, session: AsyncSession, model_key: str):
        stmt = select(CodifierElement).join(ExamModel).where(ExamModel.model_key == model_key).order_by(CodifierElement.code)
        rows = await session.execute(stmt)
        return rows.scalars().all()

    async def get_topic_mappings(self, session: AsyncSession, topic_id: uuid.UUID):
        stmt = (
            select(TopicExamMapping)
            .where(TopicExamMapping.topic_id == topic_id)
            .options(selectinload(TopicExamMapping.exam_model), selectinload(TopicExamMapping.codifier_element))
        )
        rows = await session.execute(stmt)
        return rows.scalars().all()
