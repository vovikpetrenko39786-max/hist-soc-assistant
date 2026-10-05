from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class LessonStatus(str, enum.Enum):
    planned = "planned"
    started = "started"
    completed = "completed"
    partially_completed = "partially_completed"
    cancelled = "cancelled"
    rescheduled = "rescheduled"


class ProgressStatus(str, enum.Enum):
    planned = "planned"
    started = "started"
    completed = "completed"
    practice = "practice"
    assessment = "assessment"
    needs_review = "needs_review"


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[uuid.UUID] = uuid_pk()
    display_name: Mapped[str] = mapped_column(String(200))
    school_name: Mapped[str | None] = mapped_column(String(300))
    default_lesson_duration: Mapped[int] = mapped_column(Integer, default=45)
    timezone: Mapped[str] = mapped_column(String(100), default="Asia/Vladivostok")
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    classes: Mapped[list["ClassGroup"]] = relationship(back_populates="teacher")


class ClassGroup(Base):
    __tablename__ = "class_groups"

    id: Mapped[uuid.UUID] = uuid_pk()
    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teachers.id"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    grade: Mapped[int] = mapped_column(Integer, index=True)
    academic_year: Mapped[str] = mapped_column(String(20))
    students_count: Mapped[int | None] = mapped_column(Integer)
    general_level: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    teacher: Mapped[Teacher] = relationship(back_populates="classes")
    class_courses: Mapped[list["ClassCourse"]] = relationship(back_populates="class_group")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(100), index=True)
    level: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = uuid_pk()
    source_key: Mapped[str | None] = mapped_column(String(150), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    author: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(String(100), index=True)
    grade: Mapped[int | None] = mapped_column(Integer, index=True)
    level: Mapped[str | None] = mapped_column(String(100))
    year: Mapped[int | None] = mapped_column(Integer)
    edition: Mapped[str | None] = mapped_column(String(100))
    publisher: Mapped[str | None] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(100), index=True)
    origin: Mapped[str | None] = mapped_column(String(100))
    access_status: Mapped[str | None] = mapped_column(String(100))
    file_path: Mapped[str | None] = mapped_column(Text)
    file_hash: Mapped[str | None] = mapped_column(String(128), unique=True)
    page_count: Mapped[int | None] = mapped_column(Integer)
    has_text_layer: Mapped[bool] = mapped_column(Boolean, default=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    fpu_number: Mapped[str | None] = mapped_column(String(100), index=True)
    isbn: Mapped[str | None] = mapped_column(String(50), index=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    authority_rank: Mapped[int] = mapped_column(Integer, default=50, index=True)
    verification_status: Mapped[str | None] = mapped_column(String(100), index=True)
    rollout_status: Mapped[str | None] = mapped_column(String(100), index=True)
    availability_status: Mapped[str | None] = mapped_column(String(100), index=True)
    coverage: Mapped[str | None] = mapped_column(String(100), index=True)
    ingestion_status: Mapped[str | None] = mapped_column(String(100), index=True)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    text_char_count: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    chunks: Mapped[list["SourceChunk"]] = relationship(back_populates="source")
    pages: Mapped[list["SourcePage"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    sections: Mapped[list["SourceSection"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    ingestion_runs: Mapped[list["SourceIngestionRun"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class ClassCourse(Base):
    __tablename__ = "class_courses"

    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("class_groups.id"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teachers.id"), index=True)
    hours_per_week: Mapped[int | None] = mapped_column(Integer)
    group_name: Mapped[str | None] = mapped_column(String(100))
    primary_source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    class_group: Mapped[ClassGroup] = relationship(back_populates="class_courses")
    course: Mapped[Course] = relationship()
    primary_source: Mapped[Source | None] = relationship()
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="class_course")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[uuid.UUID] = uuid_pk()
    class_course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("class_courses.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    lesson_number: Mapped[int | None] = mapped_column(Integer)
    topic: Mapped[str] = mapped_column(String(500))
    lesson_type: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[LessonStatus] = mapped_column(
        Enum(LessonStatus, name="lesson_status"), default=LessonStatus.planned, index=True
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, default=45)
    planned_content: Mapped[str | None] = mapped_column(Text)
    completed_content: Mapped[str | None] = mapped_column(Text)
    unfinished_content: Mapped[str | None] = mapped_column(Text)
    reflection: Mapped[str | None] = mapped_column(Text)
    next_step: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    class_course: Mapped[ClassCourse] = relationship(back_populates="lessons")


class CurriculumProgress(Base):
    __tablename__ = "curriculum_progress"

    id: Mapped[uuid.UUID] = uuid_pk()
    class_course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("class_courses.id"), index=True)
    unit: Mapped[str | None] = mapped_column(String(300))
    topic: Mapped[str] = mapped_column(String(500))
    subtopic: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[ProgressStatus] = mapped_column(
        Enum(ProgressStatus, name="progress_status"),
        default=ProgressStatus.planned,
        index=True,
    )
    started_at: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[date | None] = mapped_column(Date)
    source_section: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Homework(Base):
    __tablename__ = "homework"

    id: Mapped[uuid.UUID] = uuid_pk()
    class_course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("class_courses.id"), index=True)
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lessons.id"), index=True)
    assigned_date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    text: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="assigned", index=True)


class SourcePage(Base):
    __tablename__ = "source_pages"
    __table_args__ = (
        UniqueConstraint("source_id", "page_number_pdf", name="uq_source_page_pdf_number"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    page_number_pdf: Mapped[int] = mapped_column(Integer, index=True)  # 1-based
    page_label: Mapped[str | None] = mapped_column(String(100))
    printed_page: Mapped[int | None] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    text_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    has_text: Mapped[bool] = mapped_column(Boolean, default=False)
    extraction_method: Mapped[str] = mapped_column(String(50), default="pymupdf")
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    source: Mapped[Source] = relationship(back_populates="pages")


class SourceSection(Base):
    __tablename__ = "source_sections"

    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    parent_section_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_sections.id"), index=True)
    toc_level: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(1000))
    start_page_pdf: Mapped[int] = mapped_column(Integer, index=True)
    end_page_pdf: Mapped[int | None] = mapped_column(Integer)
    printed_page_start: Mapped[int | None] = mapped_column(Integer)
    printed_page_end: Mapped[int | None] = mapped_column(Integer)
    order_index: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    source: Mapped[Source] = relationship(back_populates="sections")
    parent_section: Mapped["SourceSection | None"] = relationship(remote_side="SourceSection.id")


class SourceIngestionRun(Base):
    __tablename__ = "source_ingestion_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    status: Mapped[str] = mapped_column(String(100), index=True)
    original_filename: Mapped[str | None] = mapped_column(String(1000))
    stored_file_path: Mapped[str | None] = mapped_column(Text)
    file_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    extraction_method: Mapped[str | None] = mapped_column(String(100))
    page_count: Mapped[int | None] = mapped_column(Integer)
    text_char_count: Mapped[int | None] = mapped_column(Integer)
    pages_with_text: Mapped[int | None] = mapped_column(Integer)
    sections_created: Mapped[int] = mapped_column(Integer, default=0)
    chunks_created: Mapped[int] = mapped_column(Integer, default=0)
    needs_ocr: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    source: Mapped[Source] = relationship(back_populates="ingestion_runs")


class SourceChunk(Base):
    __tablename__ = "source_chunks"

    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    section_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_sections.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    chapter: Mapped[str | None] = mapped_column(String(300))
    section: Mapped[str | None] = mapped_column(String(300))
    paragraph: Mapped[str | None] = mapped_column(String(300))
    topic: Mapped[str | None] = mapped_column(String(300), index=True)
    page_pdf: Mapped[int | None] = mapped_column(Integer)
    page_pdf_end: Mapped[int | None] = mapped_column(Integer)
    page_print: Mapped[int | None] = mapped_column(Integer)
    page_print_end: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(100), default="main_text")
    text: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    char_count: Mapped[int | None] = mapped_column(Integer)
    embedding_status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    embedding_model: Mapped[str | None] = mapped_column(String(200), index=True)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, index=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    embedding: Mapped[list[float] | None] = mapped_column(Vector())
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    source: Mapped[Source] = relationship(back_populates="chunks")
    source_section: Mapped[SourceSection | None] = relationship()


class GeneratedMaterial(Base):
    __tablename__ = "generated_materials"

    id: Mapped[uuid.UUID] = uuid_pk()
    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teachers.id"), index=True)
    class_course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("class_courses.id"), index=True
    )
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lessons.id"), index=True)
    material_type: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class GenerationRun(Base):
    __tablename__ = "generation_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    task_type: Mapped[str] = mapped_column(String(100), index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"), index=True)
    class_course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("class_courses.id"), index=True
    )
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teachers.id"), index=True
    )
    provider: Mapped[str] = mapped_column(String(100), index=True)
    model: Mapped[str] = mapped_column(String(200), index=True)
    prompt_hash: Mapped[str] = mapped_column(String(128), index=True)
    request_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    context_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    source_manifest: Mapped[list] = mapped_column(JSONB, default=list)
    output_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    quality_report: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="created", index=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )


class ExportedFile(Base):
    __tablename__ = "exported_files"

    id: Mapped[uuid.UUID] = uuid_pk()
    generation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("generation_runs.id"), index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(100), index=True)
    audience: Mapped[str] = mapped_column(String(50), index=True)
    file_format: Mapped[str] = mapped_column(String(20), index=True)
    template_name: Mapped[str] = mapped_column(String(100), index=True)
    template_version: Mapped[str] = mapped_column(String(50))
    file_path: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="ready", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )


class WebSearchRun(Base):
    __tablename__ = "web_search_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"), index=True)
    generation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("generation_runs.id"), index=True
    )
    policy: Mapped[str] = mapped_column(String(50), index=True)
    scope: Mapped[str] = mapped_column(String(50), index=True)
    provider: Mapped[str] = mapped_column(String(100), index=True)
    model: Mapped[str] = mapped_column(String(200), index=True)
    query: Mapped[str] = mapped_column(Text)
    allowed_domains: Mapped[list] = mapped_column(JSONB, default=list)
    response_text: Mapped[str | None] = mapped_column(Text)
    sources_json: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(50), default="created", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PilotFeedback(Base):
    __tablename__ = "pilot_feedback"

    id: Mapped[uuid.UUID] = uuid_pk()
    channel: Mapped[str] = mapped_column(String(50), default="telegram", index=True)
    category: Mapped[str] = mapped_column(String(50), default="feedback", index=True)
    user_external_id: Mapped[str | None] = mapped_column(String(200), index=True)
    username: Mapped[str | None] = mapped_column(String(200), index=True)
    display_name: Mapped[str | None] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    last_request: Mapped[str | None] = mapped_column(Text)
    generation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("generation_runs.id"), index=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
