from __future__ import annotations
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

class Subject(Base):
    __tablename__ = 'subjects'
    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    curricula: Mapped[list['Curriculum']] = relationship(back_populates='subject')

class GradeLevel(Base):
    __tablename__ = 'grade_levels'
    id: Mapped[uuid.UUID] = uuid_pk()
    grade: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    education_level: Mapped[str] = mapped_column(String(100), index=True)
    label: Mapped[str | None] = mapped_column(String(100))
    curricula: Mapped[list['Curriculum']] = relationship(back_populates='grade_level')

class Curriculum(Base):
    __tablename__ = 'curricula'
    __table_args__ = (UniqueConstraint('subject_id','grade_level_id','level','version', name='uq_curriculum_version'),)
    id: Mapped[uuid.UUID] = uuid_pk()
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('subjects.id'), index=True)
    grade_level_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('grade_levels.id'), index=True)
    level: Mapped[str] = mapped_column(String(100), default='basic', index=True)
    title: Mapped[str] = mapped_column(String(500))
    version: Mapped[str] = mapped_column(String(100), default='v1')
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), default='current', index=True)
    official_source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('sources.id'))
    review_status: Mapped[str] = mapped_column(String(50), default='draft', index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    subject: Mapped[Subject] = relationship(back_populates='curricula')
    grade_level: Mapped[GradeLevel] = relationship(back_populates='curricula')
    official_source = relationship('Source')
    units: Mapped[list['CurriculumUnit']] = relationship(back_populates='curriculum', order_by='CurriculumUnit.order_index')

class CurriculumUnit(Base):
    __tablename__ = 'curriculum_units'
    __table_args__ = (UniqueConstraint('curriculum_id','order_index', name='uq_unit_order'),)
    id: Mapped[uuid.UUID] = uuid_pk()
    curriculum_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('curricula.id'), index=True)
    title: Mapped[str] = mapped_column(String(500))
    order_index: Mapped[int] = mapped_column(Integer, index=True)
    recommended_hours: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    source_reference: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(50), default='draft', index=True)
    curriculum: Mapped[Curriculum] = relationship(back_populates='units')
    topics: Mapped[list['Topic']] = relationship(back_populates='unit', order_by='Topic.order_index')

class Topic(Base):
    __tablename__ = 'topics'
    __table_args__ = (UniqueConstraint('unit_id','order_index', name='uq_topic_order'),)
    id: Mapped[uuid.UUID] = uuid_pk()
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('curriculum_units.id'), index=True)
    parent_topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('topics.id'), index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    aliases: Mapped[list] = mapped_column(JSONB, default=list)
    order_index: Mapped[int] = mapped_column(Integer, index=True)
    recommended_hours: Mapped[int | None] = mapped_column(Integer)
    topic_type: Mapped[str] = mapped_column(String(100), default='new_content')
    description: Mapped[str | None] = mapped_column(Text)
    default_lesson_blueprint: Mapped[dict] = mapped_column(JSONB, default=dict)
    typical_misconceptions: Mapped[list] = mapped_column(JSONB, default=list)
    common_examples: Mapped[list] = mapped_column(JSONB, default=list)
    counterexamples: Mapped[list] = mapped_column(JSONB, default=list)
    essential_questions: Mapped[list] = mapped_column(JSONB, default=list)
    reflection_patterns: Mapped[list] = mapped_column(JSONB, default=list)
    assessment_skills: Mapped[list] = mapped_column(JSONB, default=list)
    difficulty_level: Mapped[int | None] = mapped_column(Integer)
    abstraction_level: Mapped[int | None] = mapped_column(Integer)
    prerequisite_topic_ids: Mapped[list] = mapped_column(JSONB, default=list)
    review_status: Mapped[str] = mapped_column(String(50), default='draft', index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    unit: Mapped[CurriculumUnit] = relationship(back_populates='topics')
    parent_topic: Mapped['Topic | None'] = relationship(remote_side='Topic.id')
    outcomes: Mapped[list['TopicOutcome']] = relationship(back_populates='topic', cascade='all, delete-orphan')
    concepts: Mapped[list['TopicConcept']] = relationship(back_populates='topic', cascade='all, delete-orphan')
    skills: Mapped[list['TopicSkill']] = relationship(back_populates='topic', cascade='all, delete-orphan')
    sources: Mapped[list['TopicSource']] = relationship(back_populates='topic', cascade='all, delete-orphan')
    interdisciplinary_links: Mapped[list['InterdisciplinaryLink']] = relationship(back_populates='topic', cascade='all, delete-orphan')
    exam_links: Mapped[list['ExamLink']] = relationship(back_populates='topic', cascade='all, delete-orphan')

class LearningOutcome(Base):
    __tablename__ = 'learning_outcomes'
    id: Mapped[uuid.UUID] = uuid_pk()
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('subjects.id'), index=True)
    grade_level_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('grade_levels.id'), index=True)
    outcome_type: Mapped[str] = mapped_column(String(100), index=True)
    outcome_subtype: Mapped[str | None] = mapped_column(String(100), index=True)
    text: Mapped[str] = mapped_column(Text)
    source_reference: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(50), default='draft', index=True)

class TopicOutcome(Base):
    __tablename__ = 'topic_outcomes'
    __table_args__ = (UniqueConstraint('topic_id','outcome_id', name='uq_topic_outcome'),)
    id: Mapped[uuid.UUID] = uuid_pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('topics.id'), index=True)
    outcome_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('learning_outcomes.id'), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    topic: Mapped[Topic] = relationship(back_populates='outcomes')
    outcome: Mapped[LearningOutcome] = relationship()

class Concept(Base):
    __tablename__ = 'concepts'
    __table_args__ = (UniqueConstraint('subject_id','term', name='uq_concept_term'),)
    id: Mapped[uuid.UUID] = uuid_pk()
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('subjects.id'), index=True)
    term: Mapped[str] = mapped_column(String(300), index=True)
    definition_reference: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

class TopicConcept(Base):
    __tablename__ = 'topic_concepts'
    __table_args__ = (UniqueConstraint('topic_id','concept_id', name='uq_topic_concept'),)
    id: Mapped[uuid.UUID] = uuid_pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('topics.id'), index=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('concepts.id'), index=True)
    importance: Mapped[str] = mapped_column(String(50), default='required')
    topic: Mapped[Topic] = relationship(back_populates='concepts')
    concept: Mapped[Concept] = relationship()

class Skill(Base):
    __tablename__ = 'skills'
    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str | None] = mapped_column(Text)

class TopicSkill(Base):
    __tablename__ = 'topic_skills'
    __table_args__ = (UniqueConstraint('topic_id','skill_id', name='uq_topic_skill'),)
    id: Mapped[uuid.UUID] = uuid_pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('topics.id'), index=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('skills.id'), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    topic: Mapped[Topic] = relationship(back_populates='skills')
    skill: Mapped[Skill] = relationship()

class InterdisciplinaryLink(Base):
    __tablename__ = 'interdisciplinary_links'
    id: Mapped[uuid.UUID] = uuid_pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('topics.id'), index=True)
    related_subject: Mapped[str] = mapped_column(String(100), index=True)
    related_topic: Mapped[str | None] = mapped_column(String(500))
    link_type: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    strength: Mapped[str] = mapped_column(String(50), default='optional')
    topic: Mapped[Topic] = relationship(back_populates='interdisciplinary_links')

class ExamLink(Base):
    __tablename__ = 'exam_links'
    id: Mapped[uuid.UUID] = uuid_pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('topics.id'), index=True)
    exam: Mapped[str] = mapped_column(String(100), index=True)
    exam_year: Mapped[int | None] = mapped_column(Integer, index=True)
    exam_section: Mapped[str | None] = mapped_column(String(300))
    task_types: Mapped[list] = mapped_column(JSONB, default=list)
    codifier_reference: Mapped[str | None] = mapped_column(Text)
    importance: Mapped[str] = mapped_column(String(50), default='normal')
    topic: Mapped[Topic] = relationship(back_populates='exam_links')

class TopicSource(Base):
    __tablename__ = 'topic_sources'
    __table_args__ = (UniqueConstraint('topic_id','source_id','source_role', name='uq_topic_source_role'),)
    id: Mapped[uuid.UUID] = uuid_pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('topics.id'), index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('sources.id'), index=True)
    source_role: Mapped[str] = mapped_column(String(100), index=True)
    section: Mapped[str | None] = mapped_column(String(500))
    pages: Mapped[str | None] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    chunk_filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[Topic] = relationship(back_populates='sources')
    source = relationship('Source')
