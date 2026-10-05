import uuid
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.catalog import Curriculum, CurriculumUnit, GradeLevel, Subject, Topic, TopicConcept, TopicOutcome, TopicSkill, TopicSource

class CurriculumCatalogService:
    async def list_subjects(self, session: AsyncSession):
        return (await session.execute(select(Subject).where(Subject.is_active.is_(True)).order_by(Subject.name))).scalars().all()

    async def list_curricula(self, session: AsyncSession, subject_code=None, grade=None, level=None, status='current'):
        stmt = select(Curriculum).join(Subject).join(GradeLevel).where(Curriculum.status == status)
        if subject_code: stmt = stmt.where(Subject.code == subject_code)
        if grade is not None: stmt = stmt.where(GradeLevel.grade == grade)
        if level: stmt = stmt.where(Curriculum.level == level)
        return (await session.execute(stmt.order_by(Subject.code, GradeLevel.grade, Curriculum.level))).scalars().all()

    async def search_topics(self, session: AsyncSession, q=None, subject_code=None, grade=None, level=None, limit=20):
        stmt = select(Topic, CurriculumUnit, Curriculum, Subject, GradeLevel).join(CurriculumUnit).join(Curriculum).join(Subject).join(GradeLevel).where(Curriculum.status == 'current')
        if subject_code: stmt = stmt.where(Subject.code == subject_code)
        if grade is not None: stmt = stmt.where(GradeLevel.grade == grade)
        if level: stmt = stmt.where(Curriculum.level == level)
        if q:
            pattern = f'%{q.lower()}%'
            stmt = stmt.where(or_(func.lower(Topic.title).like(pattern), func.lower(cast(Topic.aliases, String)).like(pattern)))
        rows = (await session.execute(stmt.order_by(Subject.code, GradeLevel.grade, CurriculumUnit.order_index, Topic.order_index).limit(limit))).all()
        return [{'id':t.id,'title':t.title,'aliases':t.aliases or [],'grade':g.grade,'subject_code':s.code,'curriculum_title':c.title,'unit_title':u.title,'review_status':t.review_status} for t,u,c,s,g in rows]

    async def get_topic_card(self, session: AsyncSession, topic_id: uuid.UUID):
        stmt = select(Topic).where(Topic.id == topic_id).options(
            selectinload(Topic.unit).selectinload(CurriculumUnit.curriculum).selectinload(Curriculum.subject),
            selectinload(Topic.unit).selectinload(CurriculumUnit.curriculum).selectinload(Curriculum.grade_level),
            selectinload(Topic.outcomes).selectinload(TopicOutcome.outcome),
            selectinload(Topic.concepts).selectinload(TopicConcept.concept),
            selectinload(Topic.skills).selectinload(TopicSkill.skill),
            selectinload(Topic.sources).selectinload(TopicSource.source),
            selectinload(Topic.interdisciplinary_links),
            selectinload(Topic.exam_links),
        )
        t = (await session.execute(stmt)).scalar_one_or_none()
        if t is None: return None
        c=t.unit.curriculum; s=c.subject; g=c.grade_level
        return {
          'topic_id':t.id,
          'subject':{'id':s.id,'code':s.code,'name':s.name},
          'grade':g.grade,
          'curriculum':{'id':c.id,'title':c.title,'level':c.level,'version':c.version,'status':c.status,'review_status':c.review_status},
          'unit':{'id':t.unit.id,'title':t.unit.title,'order_index':t.unit.order_index,'recommended_hours':t.unit.recommended_hours},
          'topic':{'id':t.id,'title':t.title,'aliases':t.aliases or [],'order_index':t.order_index,'recommended_hours':t.recommended_hours,'topic_type':t.topic_type,'description':t.description,'default_lesson_blueprint':t.default_lesson_blueprint or {},'typical_misconceptions':t.typical_misconceptions or [],'common_examples':t.common_examples or [],'counterexamples':t.counterexamples or [],'essential_questions':t.essential_questions or [],'reflection_patterns':t.reflection_patterns or [],'assessment_skills':t.assessment_skills or [],'difficulty_level':t.difficulty_level,'abstraction_level':t.abstraction_level,'prerequisite_topic_ids':t.prerequisite_topic_ids or [],'review_status':t.review_status},
          'outcomes':[{'id':x.outcome.id,'type':x.outcome.outcome_type,'subtype':x.outcome.outcome_subtype,'text':x.outcome.text,'source_reference':x.outcome.source_reference,'priority':x.priority} for x in t.outcomes],
          'concepts':[{'id':x.concept.id,'term':x.concept.term,'importance':x.importance,'definition_reference':x.concept.definition_reference} for x in t.concepts],
          'skills':[{'id':x.skill.id,'code':x.skill.code,'name':x.skill.name,'category':x.skill.category,'priority':x.priority} for x in t.skills],
          'sources':[{'id':x.source.id,'title':x.source.title,'author':x.source.author,'source_role':x.source_role,'section':x.section,'pages':x.pages,'priority':x.priority,'origin':x.source.origin,'status':x.source.status} for x in t.sources],
          'interdisciplinary_links':[{'related_subject':x.related_subject,'related_topic':x.related_topic,'link_type':x.link_type,'description':x.description,'strength':x.strength} for x in t.interdisciplinary_links],
          'exam_links':[{'exam':x.exam,'exam_year':x.exam_year,'exam_section':x.exam_section,'task_types':x.task_types or [],'codifier_reference':x.codifier_reference,'importance':x.importance} for x in t.exam_links],
        }
