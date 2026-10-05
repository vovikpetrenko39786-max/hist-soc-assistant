from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class ExamModel(Base):
    __tablename__ = "exam_models"

    id: Mapped[uuid.UUID] = uuid_pk()
    model_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    exam: Mapped[str] = mapped_column(String(30), index=True)  # EGE / OGE
    subject: Mapped[str] = mapped_column(String(100), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)  # project / final / archive
    total_tasks: Mapped[int | None] = mapped_column(Integer)
    max_primary_score: Mapped[int | None] = mapped_column(Integer)
    source_url: Mapped[str] = mapped_column(Text)
    change_source_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    resources: Mapped[list["ExamResource"]] = relationship(back_populates="exam_model", cascade="all, delete-orphan")
    codifier_elements: Mapped[list["CodifierElement"]] = relationship(back_populates="exam_model", cascade="all, delete-orphan")
    tasks: Mapped[list["ExamTask"]] = relationship(back_populates="exam_model", cascade="all, delete-orphan")
    topic_mappings: Mapped[list["TopicExamMapping"]] = relationship(back_populates="exam_model", cascade="all, delete-orphan")


class ExamResource(Base):
    __tablename__ = "exam_resources"
    __table_args__ = (UniqueConstraint("exam_model_id", "resource_type", "url", name="uq_exam_resource"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    exam_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_models.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text)
    source_year: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="official")
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    exam_model: Mapped[ExamModel] = relationship(back_populates="resources")


class CodifierElement(Base):
    __tablename__ = "codifier_elements"
    __table_args__ = (UniqueConstraint("exam_model_id", "code", name="uq_exam_codifier_code"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    exam_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_models.id"), index=True)
    code: Mapped[str] = mapped_column(String(50), index=True)
    section: Mapped[str | None] = mapped_column(String(300), index=True)
    normalized_label: Mapped[str] = mapped_column(Text)
    source_reference: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(80), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    exam_model: Mapped[ExamModel] = relationship(back_populates="codifier_elements")
    topic_mappings: Mapped[list["TopicExamMapping"]] = relationship(back_populates="codifier_element")


class ExamTask(Base):
    __tablename__ = "exam_tasks"
    __table_args__ = (UniqueConstraint("exam_model_id", "task_key", name="uq_exam_task_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    exam_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_models.id"), index=True)
    task_key: Mapped[str] = mapped_column(String(80), index=True)
    task_number: Mapped[int | None] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(500))
    response_type: Mapped[str | None] = mapped_column(String(100))
    max_score: Mapped[int | None] = mapped_column(Integer)
    skill_codes: Mapped[list] = mapped_column(JSONB, default=list)
    content_scope: Mapped[dict] = mapped_column(JSONB, default=dict)
    verification_status: Mapped[str] = mapped_column(String(80), index=True)
    source_reference: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    exam_model: Mapped[ExamModel] = relationship(back_populates="tasks")


class TopicExamMapping(Base):
    __tablename__ = "topic_exam_mappings"
    __table_args__ = (
        UniqueConstraint("topic_id", "exam_model_id", "codifier_element_id", name="uq_topic_exam_codifier"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"), index=True)
    exam_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_models.id"), index=True)
    codifier_element_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("codifier_elements.id"), index=True)
    task_keys: Mapped[list] = mapped_column(JSONB, default=list)
    mapping_status: Mapped[str] = mapped_column(String(80), index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence_type: Mapped[str] = mapped_column(String(80))
    evidence_reference: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    topic = relationship("Topic")
    exam_model: Mapped[ExamModel] = relationship(back_populates="topic_mappings")
    codifier_element: Mapped[CodifierElement | None] = relationship(back_populates="topic_mappings")
