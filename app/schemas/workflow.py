from typing import Literal

from pydantic import BaseModel, Field


class NaturalWorkflowRequest(BaseModel):
    message: str = Field(min_length=1, max_length=15000)
    dry_run: bool = False
    auto_render: bool = True
    template_name: str = "school_clean"
    allow_web_fallback: bool = True
    default_formats: list[Literal["docx", "pdf"]] = Field(default_factory=list)
    client_context: dict = Field(default_factory=dict)


class ParsedArtifact(BaseModel):
    artifact_type: Literal[
        "lesson",
        "assessment",
        "worksheet",
        "homework",
        "idea_enhancement",
    ]
    audience: Literal["teacher", "student", "both"] = "teacher"


class WorkflowPlan(BaseModel):
    original_message: str
    subject: str | None = None
    grade: int | None = None
    class_label: str | None = None
    level: str | None = None
    topic: str | None = None
    duration_minutes: int | None = None
    mode: Literal["practical", "full", "formal", "emergency"] = "practical"
    artifacts: list[ParsedArtifact]
    formats: list[Literal["docx", "pdf"]] = Field(default_factory=list)
    template_name: str = "school_clean"
    strict_source: bool = False
    source_key: str | None = None
    assessment_task_count: int | None = None
    assessment_max_points: int | None = None
    knowledge_policy: Literal[
        "library_only",
        "library_first",
        "official_web_first",
    ] = "library_first"
    web_fallback_allowed: bool = True
    parser_confidence: float = Field(ge=0, le=1)
    notes: list[str] = Field(default_factory=list)


class WorkflowFile(BaseModel):
    export_id: str | None = None
    file_name: str
    file_format: str
    audience: str
    download_path: str | None = None


class WorkflowArtifactResult(BaseModel):
    artifact_type: str
    status: str
    run_id: str | None = None
    quality_score: int | None = None
    files: list[WorkflowFile] = Field(default_factory=list)
    web_used: bool = False
    web_source_count: int = 0
    web_sources: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class NaturalWorkflowResponse(BaseModel):
    status: Literal["planned", "completed", "partial", "failed"]
    plan: WorkflowPlan
    results: list[WorkflowArtifactResult] = Field(default_factory=list)
    summary: str
    warnings: list[str] = Field(default_factory=list)
