import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_serializer, model_validator


class LessonGenerationRequest(BaseModel):
    request_text: str = Field(default="", max_length=10000)

    subject: str | None = None
    grade: int | None = Field(default=None, ge=1, le=11)
    level: str | None = None

    topic_id: uuid.UUID | None = None
    topic: str | None = None

    duration_minutes: int = Field(default=45, ge=20, le=120)
    mode: Literal["practical", "full", "formal", "emergency"] = "practical"

    source_key: str | None = None
    strict_source: bool = False
    retrieval_mode: Literal["hybrid", "lexical", "vector", "exact"] = "hybrid"
    retrieval_top_k: int = Field(default=8, ge=1, le=20)

    include_exam_perspective: bool = True
    save_run: bool = True
    dry_run: bool = False

    @model_validator(mode="after")
    def validate_topic_and_source(self):
        if not self.topic_id and not self.topic:
            raise ValueError("topic_id or topic is required")
        if self.strict_source and not self.source_key:
            raise ValueError("strict_source=true requires source_key")
        return self


class LessonTimelineStep(BaseModel):
    minutes: int = Field(ge=1)
    stage: str
    teacher_action: str
    student_action: str
    evidence_of_learning: str | None = None


class LessonFgosAlignment(BaseModel):
    """Operational alignment for a teachable lesson, not a compliance claim."""

    subject_results: list[str]
    meta_subject_results: list[str]
    personal_results: list[str]
    learning_activities: list[str]
    assessment_evidence: list[str]


class TeacherNarrativeBlock(BaseModel):
    stage: str
    purpose: str
    teacher_script: list[str]
    student_prompts: list[str]
    board_notes: list[str]
    attention_points: list[str]


class AnticipatedStudentQuestion(BaseModel):
    question: str
    short_answer: str
    expanded_answer: str
    teaching_note: str


class MisconceptionSupport(BaseModel):
    misconception: str
    diagnostic_question: str
    correction: str
    example_or_counterexample: str


class LessonVariant(BaseModel):
    approach: Literal["teacher_explanation", "textbook_independent", "group_work"]
    title: str
    when_to_use: str
    preparation: list[str]
    steps: list[str]
    evidence_of_learning: str
    risks_and_mitigation: list[str]


class SourceReference(BaseModel):
    chunk_id: str
    source_id: str
    source_key: str | None = None
    title: str
    url: str | None = None
    section: str | None = None
    page_pdf_start: int | None = None
    page_pdf_end: int | None = None
    page_print_start: int | None = None
    page_print_end: int | None = None
    quote_safe: bool = False


class LessonArtifact(BaseModel):
    title: str
    grade: int
    subject: str
    duration_minutes: int

    essential_question: str | None = None
    goal: str
    measurable_outcomes: list[str]
    key_concepts: list[str]

    timeline: list[LessonTimelineStep]

    fgos_alignment: LessonFgosAlignment
    materials: list[str]
    teacher_narrative: list[TeacherNarrativeBlock]
    anticipated_student_questions: list[AnticipatedStudentQuestion]
    misconception_support: list[MisconceptionSupport]
    lesson_variants: list[LessonVariant]
    recommended_variant: Literal[
        "teacher_explanation", "textbook_independent", "group_work"
    ]
    methodical_notes: list[str]

    notebook: list[str] = Field(default_factory=list)
    differentiation: list[str] = Field(default_factory=list)
    formative_check: list[str] = Field(default_factory=list)
    reflection: list[str] = Field(default_factory=list)
    homework: str | None = None
    reserve_task: str | None = None
    cut_first_if_short_on_time: list[str] = Field(default_factory=list)
    exam_perspective: list[str] = Field(default_factory=list)

    source_references: list[SourceReference] = Field(default_factory=list)


class TopicEnrichmentExample(BaseModel):
    title: str
    description: str


class TopicEnrichmentActivity(BaseModel):
    activity: str
    purpose: str
    student_action: str
    # Optional on load for existing hashed candidates; required for new generation.
    expected_answer: str | None = None
    assessment_criteria: list[str] | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_shape(self, handler):
        data = handler(self)
        for field in ("expected_answer", "assessment_criteria"):
            if field not in self.model_fields_set:
                data.pop(field, None)
        return data


class TopicEnrichmentArtifact(BaseModel):
    content_summary: str
    common_examples: list[TopicEnrichmentExample]
    counterexamples: list[TopicEnrichmentExample]
    typical_misconceptions: list[str]
    essential_questions: list[str]
    suitable_activities: list[TopicEnrichmentActivity]


class QualityCheck(BaseModel):
    code: str
    passed: bool
    severity: Literal["info", "warning", "error"]
    message: str


class QualityReport(BaseModel):
    passed: bool
    score: int = Field(ge=0, le=100)
    checks: list[QualityCheck]
    warnings: list[str] = Field(default_factory=list)


class GroundedLessonResponse(BaseModel):
    status: Literal["dry_run", "generated", "quality_failed"]
    topic_card: dict
    retrieval: dict
    generation_context: dict
    artifact: LessonArtifact | None = None
    quality: QualityReport | None = None
    run_id: uuid.UUID | None = None
