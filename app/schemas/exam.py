import uuid
from pydantic import BaseModel, Field


class ExamModelOut(BaseModel):
    model_key: str
    exam: str
    subject: str
    year: int
    status: str
    total_tasks: int | None = None
    max_primary_score: int | None = None
    notes: str | None = None
    metadata_json: dict = Field(default_factory=dict)


class ExamTaskOut(BaseModel):
    task_key: str
    task_number: int | None = None
    title: str
    response_type: str | None = None
    max_score: int | None = None
    skill_codes: list = Field(default_factory=list)
    verification_status: str
    source_reference: str
    notes: str | None = None


class CodifierElementOut(BaseModel):
    code: str
    section: str | None = None
    normalized_label: str
    verification_status: str
    source_reference: str


class TopicExamMappingOut(BaseModel):
    exam_model_key: str
    codifier_code: str | None = None
    task_keys: list = Field(default_factory=list)
    mapping_status: str
    confidence: float | None = None
    evidence_type: str
    evidence_reference: str | None = None
    notes: str | None = None
