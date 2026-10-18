import uuid
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.catalog import (
    Concept,
    Curriculum,
    CurriculumUnit,
    ExamLink,
    GradeLevel,
    InterdisciplinaryLink,
    LearningOutcome,
    Skill,
    Subject,
    Topic,
    TopicConcept,
    TopicOutcome,
    TopicSkill,
    TopicSource,
)
from app.models.entities import Source

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
        stmt = (
            select(Topic, CurriculumUnit, Curriculum, Subject, GradeLevel)
            .select_from(Topic)
            .join(CurriculumUnit, Topic.unit_id == CurriculumUnit.id)
            .join(Curriculum, CurriculumUnit.curriculum_id == Curriculum.id)
            .join(Subject, Curriculum.subject_id == Subject.id)
            .join(GradeLevel, Curriculum.grade_level_id == GradeLevel.id)
            .where(Curriculum.status == 'current')
        )
        if subject_code: stmt = stmt.where(Subject.code == subject_code)
        if grade is not None: stmt = stmt.where(GradeLevel.grade == grade)
        if level: stmt = stmt.where(Curriculum.level == level)
        if q:
            pattern = f'%{q.lower()}%'
            stmt = stmt.where(or_(func.lower(Topic.title).like(pattern), func.lower(cast(Topic.aliases, String)).like(pattern)))
        rows = (await session.execute(stmt.order_by(Subject.code, GradeLevel.grade, CurriculumUnit.order_index, Topic.order_index).limit(limit))).all()
        return [{'id':t.id,'title':t.title,'aliases':t.aliases or [],'grade':g.grade,'subject_code':s.code,'curriculum_title':c.title,'unit_title':u.title,'review_status':t.review_status} for t,u,c,s,g in rows]

    async def get_topic_card(self, session: AsyncSession, topic_id: uuid.UUID):
        topic_stmt = select(Topic).select_from(Topic).where(Topic.id == topic_id)
        t = (await session.execute(topic_stmt)).scalar_one_or_none()
        if t is None: return None

        unit_stmt = (
            select(CurriculumUnit, Curriculum, Subject, GradeLevel)
            .select_from(CurriculumUnit)
            .join(Curriculum, CurriculumUnit.curriculum_id == Curriculum.id)
            .join(Subject, Curriculum.subject_id == Subject.id)
            .join(GradeLevel, Curriculum.grade_level_id == GradeLevel.id)
            .where(CurriculumUnit.id == t.unit_id)
        )
        unit_row = (await session.execute(unit_stmt)).one_or_none()
        if unit_row is None:
            return None
        unit, c, s, g = unit_row

        outcome_stmt = (
            select(TopicOutcome, LearningOutcome)
            .select_from(TopicOutcome)
            .join(LearningOutcome, TopicOutcome.outcome_id == LearningOutcome.id)
            .where(TopicOutcome.topic_id == t.id)
            .order_by(TopicOutcome.priority)
        )
        outcome_rows = (await session.execute(outcome_stmt)).all()
        concept_stmt = (
            select(TopicConcept, Concept)
            .select_from(TopicConcept)
            .join(Concept, TopicConcept.concept_id == Concept.id)
            .where(TopicConcept.topic_id == t.id)
        )
        concept_rows = (await session.execute(concept_stmt)).all()
        skill_stmt = (
            select(TopicSkill, Skill)
            .select_from(TopicSkill)
            .join(Skill, TopicSkill.skill_id == Skill.id)
            .where(TopicSkill.topic_id == t.id)
            .order_by(TopicSkill.priority)
        )
        skill_rows = (await session.execute(skill_stmt)).all()
        source_stmt = (
            select(TopicSource, Source)
            .select_from(TopicSource)
            .join(Source, TopicSource.source_id == Source.id)
            .where(TopicSource.topic_id == t.id)
            .order_by(TopicSource.priority)
        )
        source_rows = (await session.execute(source_stmt)).all()
        interdisciplinary_stmt = (
            select(InterdisciplinaryLink)
            .select_from(InterdisciplinaryLink)
            .where(InterdisciplinaryLink.topic_id == t.id)
        )
        interdisciplinary_links = (await session.execute(interdisciplinary_stmt)).scalars().all()
        exam_stmt = (
            select(ExamLink)
            .select_from(ExamLink)
            .where(ExamLink.topic_id == t.id)
            .order_by(ExamLink.exam, ExamLink.exam_year)
        )
        exam_links = (await session.execute(exam_stmt)).scalars().all()

        outcomes=[{'id':outcome.id,'type':outcome.outcome_type,'subtype':outcome.outcome_subtype,'text':outcome.text,'source_reference':outcome.source_reference,'priority':link.priority} for link,outcome in outcome_rows]
        concepts=[{'id':concept.id,'term':concept.term,'importance':link.importance,'definition_reference':concept.definition_reference} for link,concept in concept_rows]
        skills=[{'id':skill.id,'code':skill.code,'name':skill.name,'category':skill.category,'priority':link.priority} for link,skill in skill_rows]
        source_references=[{
            'id':source.id,
            'source_key':source.source_key,
            'title':source.title,
            'url':source.source_url or (source.metadata_json or {}).get('official_url'),
            'verification_status':source.verification_status,
            'source_role':link.source_role,
            'section':link.section,
            'pages':link.pages,
            'priority':link.priority,
            'origin':source.origin,
            'status':source.status,
        } for link,source in source_rows]
        activities=t.suitable_activities or (t.default_lesson_blueprint or {}).get('recommended_activities', [])
        return {
          'topic_id':t.id,
          'subject':{'id':s.id,'code':s.code,'name':s.name},
          'grade':g.grade,
          'level':c.level,
          'hours':t.recommended_hours,
          'curriculum':{'id':c.id,'title':c.title,'level':c.level,'version':c.version,'status':c.status,'review_status':c.review_status},
          'unit':{'id':unit.id,'title':unit.title,'order_index':unit.order_index,'recommended_hours':unit.recommended_hours},
          'topic':{'id':t.id,'title':t.title,'aliases':t.aliases or [],'order_index':t.order_index,'recommended_hours':t.recommended_hours,'topic_type':t.topic_type,'description':t.description,'default_lesson_blueprint':t.default_lesson_blueprint or {},'typical_misconceptions':t.typical_misconceptions or [],'common_examples':t.common_examples or [],'counterexamples':t.counterexamples or [],'essential_questions':t.essential_questions or [],'reflection_patterns':t.reflection_patterns or [],'assessment_skills':t.assessment_skills or [],'difficulty_level':t.difficulty_level,'abstraction_level':t.abstraction_level,'prerequisite_topic_ids':t.prerequisite_topic_ids or [],'review_status':t.review_status},
          'aliases':t.aliases or [],
          'content_summary':t.content_summary,
          'learning_outcomes':outcomes,
          'key_concepts':concepts,
          'typical_misconceptions':t.typical_misconceptions or [],
          'common_examples':t.common_examples or [],
          'counterexamples':t.counterexamples or [],
          'essential_questions':t.essential_questions or [],
          'suitable_activities':activities,
          'provenance':t.provenance or {},
          'derivation_status':t.derivation_status,
          'verification_status':t.verification_status,
          'outcomes':outcomes,
          'concepts':concepts,
          'skills':skills,
          'sources':source_references,
          'source_references':source_references,
          'interdisciplinary_links':[{'related_subject':x.related_subject,'related_topic':x.related_topic,'link_type':x.link_type,'description':x.description,'strength':x.strength} for x in interdisciplinary_links],
          'exam_links':[{'exam':x.exam,'exam_year':x.exam_year,'exam_section':x.exam_section,'task_types':x.task_types or [],'codifier_reference':x.codifier_reference,'importance':x.importance} for x in exam_links],
        }
