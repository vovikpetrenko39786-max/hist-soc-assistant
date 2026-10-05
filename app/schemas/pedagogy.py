import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator


ArtifactType = Literal["lesson", "assessment", "worksheet", "homework", "idea_enhancement"]
Audience = Literal["teacher", "student", "both"]
GenerationMode = Literal["practical", "full", "formal", "emergency"]


class AssessmentSpec(BaseModel):
    task_count: int = Field(default=6, ge=1, le=30)
    max_points: int = Field(default=20, ge=1, le=100)
    difficulty: Literal["basic", "mixed", "advanced"] = "mixed"
    assessment_type: Literal[
        "mini_practice", "independent", "check", "control", "diagnostic", "exam_practice"
    ] = "check"
    include_scale: bool = True


class WorksheetSpec(BaseModel):
    target_pages: int = Field(default=2, ge=1, le=8)
    include_answer_space: bool = True
    differentiation: bool = True


class HomeworkSpec(BaseModel):
    duration_minutes: int = Field(default=15, ge=5, le=90)
    purpose: Literal[
        "consolidation", "preparation", "practice", "reflection", "research", "exam_practice"
    ] = "consolidation"


class SourceReference(BaseModel):
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    source_key: str | None = None
    title: str
    section: str | None = None
    page_pdf_start: int | None = None
    page_pdf_end: int | None = None
    page_print_start: int | None = None
    page_print_end: int | None = None
    quote_safe: bool = False


class TaskItem(BaseModel):
    number: int
    instruction: str
    skill: str | None = None
    difficulty: Literal["basic", "advanced", "high"] = "basic"
    points: int = Field(default=1, ge=0)
    student_data: str | None = None
    answer: str | None = None
    criteria: str | None = None


class LessonTimelineStep(BaseModel):
    minutes: int = Field(ge=1)
    stage: str
    teacher_action: str
    student_action: str
    evidence_of_learning: str | None = None


class LessonArtifact(BaseModel):
    artifact_type: Literal["lesson"] = "lesson"
    title: str
    grade: int
    subject: str
    duration_minutes: int
    essential_question: str | None = None
    goal: str
    measurable_outcomes: list[str]
    key_concepts: list[str]
    timeline: list[LessonTimelineStep]
    notebook: list[str] = Field(default_factory=list)
    differentiation: list[str] = Field(default_factory=list)
    formative_check: list[str] = Field(default_factory=list)
    reflection: list[str] = Field(default_factory=list)
    homework: str | None = None
    reserve_task: str | None = None
    cut_first_if_short_on_time: list[str] = Field(default_factory=list)
    exam_perspective: list[str] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)


class AssessmentArtifact(BaseModel):
    artifact_type: Literal["assessment"] = "assessment"
    title: str
    grade: int
    subject: str
    assessment_type: str
    time_minutes: int
    instructions: str
    tasks: list[TaskItem]
    max_points: int
    grading_scale: dict[str, str] = Field(default_factory=dict)
    common_errors_to_watch: list[str] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)


class WorksheetSection(BaseModel):
    title: str
    instruction: str
    tasks: list[TaskItem]


class WorksheetArtifact(BaseModel):
    artifact_type: Literal["worksheet"] = "worksheet"
    title: str
    grade: int
    subject: str
    purpose: str
    target_pages: int
    sections: list[WorksheetSection]
    support_box: list[str] = Field(default_factory=list)
    reflection: list[str] = Field(default_factory=list)
    teacher_key: list[str] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)


class HomeworkArtifact(BaseModel):
    artifact_type: Literal["homework"] = "homework"
    title: str
    grade: int
    subject: str
    purpose: str
    estimated_minutes: int
    student_instruction: str
    success_criteria: list[str]
    optional_challenge: str | None = None
    teacher_note: str | None = None
    source_references: list[SourceReference] = Field(default_factory=list)


class IdeaOption(BaseModel):
    label: Literal["minimal", "optimal", "bold"]
    description: str
    implementation: list[str]
    risks: list[str] = Field(default_factory=list)


class IdeaEnhancementArtifact(BaseModel):
    artifact_type: Literal["idea_enhancement"] = "idea_enhancement"
    original_idea: str
    pedagogical_value: list[str]
    weaknesses_or_risks: list[str]
    recommended_result: str
    options: list[IdeaOption]
    recommended_option: str
    preserve_core: str
    source_references: list[SourceReference] = Field(default_factory=list)


class PedagogyGenerationRequest(BaseModel):
    artifact_type: ArtifactType
    request_text: str = Field(default="", max_length=12000)
    subject: str | None = None
    grade: int | None = Field(default=None, ge=1, le=11)
    level: str | None = None
    topic_id: uuid.UUID | None = None
    topic: str | None = None
    audience: Audience = "teacher"
    duration_minutes: int | None = Field(default=None, ge=5, le=180)
    mode: GenerationMode = "practical"
    source_key: str | None = None
    strict_source: bool = False
    retrieval_mode: Literal["hybrid", "lexical", "vector", "exact"] = "hybrid"
    retrieval_top_k: int = Field(default=8, ge=1, le=20)
    include_exam_perspective: bool = True
    knowledge_policy: Literal[
        "library_only", "library_first", "official_web_first"
    ] = "library_first"
    allow_web_fallback: bool = True
    assessment: AssessmentSpec | None = None
    worksheet: WorksheetSpec | None = None
    homework: HomeworkSpec | None = None
    dry_run: bool = False
    save_run: bool = True

    @model_validator(mode="after")
    def validate_request(self):
        if self.artifact_type != "idea_enhancement" and not self.topic_id and not self.topic:
            raise ValueError("topic_id or topic is required")
        if self.artifact_type == "idea_enhancement" and not self.request_text.strip():
            raise ValueError("request_text is required for idea_enhancement")
        if self.strict_source and not self.source_key:
            raise ValueError("strict_source=true requires source_key")
        if self.artifact_type == "lesson" and self.duration_minutes is None:
            self.duration_minutes = 45
        if self.artifact_type == "assessment" and self.assessment is None:
            self.assessment = AssessmentSpec()
        if self.artifact_type == "worksheet" and self.worksheet is None:
            self.worksheet = WorksheetSpec()
        if self.artifact_type == "homework" and self.homework is None:
            self.homework = HomeworkSpec()
        return self


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


class PedagogyGenerationResponse(BaseModel):
    status: Literal["dry_run", "generated", "quality_failed"]
    artifact_type: ArtifactType
    topic_card: dict | None = None
    retrieval: dict | None = None
    web_retrieval: dict | None = None
    generation_context: dict
    teacher_artifact: dict | None = None
    student_artifact: dict | None = None
    quality: QualityReport | None = None
    run_id: uuid.UUID | None = None
