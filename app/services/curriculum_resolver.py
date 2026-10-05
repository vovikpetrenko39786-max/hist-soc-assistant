from __future__ import annotations

import re
import uuid

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Curriculum, CurriculumUnit, GradeLevel, Subject, Topic


class CurriculumResolutionError(RuntimeError):
    pass


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[\wа-яё]+", text.casefold(), flags=re.UNICODE))


def _token_score(query: str, candidate: str) -> float:
    q = set(_norm(query).split())
    c = set(_norm(candidate).split())
    if not q or not c:
        return 0.0
    return len(q & c) / len(q | c)


class CurriculumResolver:
    async def resolve_topic(
        self,
        session: AsyncSession,
        *,
        topic_id: uuid.UUID | None = None,
        topic_text: str | None = None,
        subject: str | None = None,
        grade: int | None = None,
        level: str | None = None,
    ) -> Topic:
        if topic_id:
            topic = await session.scalar(select(Topic).where(Topic.id == topic_id))
            if topic is None:
                raise CurriculumResolutionError("Topic not found")
            return topic

        if not topic_text:
            raise CurriculumResolutionError("Topic text is required")

        stmt = (
            select(Topic, Curriculum, Subject, GradeLevel)
            .join(CurriculumUnit, Topic.unit_id == CurriculumUnit.id)
            .join(Curriculum, CurriculumUnit.curriculum_id == Curriculum.id)
            .join(Subject, Curriculum.subject_id == Subject.id)
            .join(GradeLevel, Curriculum.grade_level_id == GradeLevel.id)
            .where(Curriculum.status == "current")
        )

        if subject:
            stmt = stmt.where(func.lower(Subject.code) == subject.lower())
        if grade is not None:
            stmt = stmt.where(GradeLevel.grade == grade)
        if level:
            stmt = stmt.where(Curriculum.level == level)

        pattern = f"%{topic_text.casefold()}%"
        direct_stmt = stmt.where(
            or_(
                func.lower(Topic.title).like(pattern),
                func.lower(cast(Topic.aliases, String)).like(pattern),
            )
        ).limit(20)

        rows = (await session.execute(direct_stmt)).all()
        if not rows:
            rows = (await session.execute(stmt.limit(300))).all()

        if not rows:
            raise CurriculumResolutionError("No curriculum topics found in the selected scope")

        query = _norm(topic_text)
        ranked = []
        for topic, curriculum, subj, grade_level in rows:
            texts = [topic.title] + list(topic.aliases or [])
            score = max((_token_score(query, text) for text in texts), default=0.0)
            if _norm(topic.title) == query:
                score += 1.0
            ranked.append((score, topic, curriculum, subj, grade_level))

        ranked.sort(key=lambda x: x[0], reverse=True)
        best = ranked[0]
        if best[0] <= 0:
            raise CurriculumResolutionError(
                f"Could not confidently resolve topic: {topic_text}"
            )

        # Ambiguity guard.
        if len(ranked) > 1 and best[0] < 1.0 and abs(best[0] - ranked[1][0]) < 0.08:
            raise CurriculumResolutionError(
                f"Ambiguous topic resolution for '{topic_text}'. "
                f"Best candidates: '{best[1].title}' and '{ranked[1][1].title}'."
            )

        return best[1]
