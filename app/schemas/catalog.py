import uuid
from pydantic import BaseModel, Field
class SubjectOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
class CurriculumOut(BaseModel):
    id: uuid.UUID
    title: str
    level: str
    version: str
    status: str
    review_status: str
class TopicSearchResult(BaseModel):
    id: uuid.UUID
    title: str
    aliases: list = Field(default_factory=list)
    grade: int
    subject_code: str
    curriculum_title: str
    unit_title: str
    review_status: str
class TopicCardOut(BaseModel):
    topic_id: uuid.UUID
    subject: dict
    grade: int
    level: str
    hours: int | None = None
    curriculum: dict
    unit: dict
    topic: dict
    aliases: list = Field(default_factory=list)
    content_summary: str | None = None
    learning_outcomes: list[dict] = Field(default_factory=list)
    key_concepts: list[dict] = Field(default_factory=list)
    typical_misconceptions: list = Field(default_factory=list)
    common_examples: list = Field(default_factory=list)
    counterexamples: list = Field(default_factory=list)
    essential_questions: list = Field(default_factory=list)
    suitable_activities: list = Field(default_factory=list)
    provenance: dict = Field(default_factory=dict)
    derivation_status: str = 'pending_enrichment'
    verification_status: str = 'pending_verification'
    outcomes: list[dict] = Field(default_factory=list)
    concepts: list[dict] = Field(default_factory=list)
    skills: list[dict] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    source_references: list[dict] = Field(default_factory=list)
    interdisciplinary_links: list[dict] = Field(default_factory=list)
    exam_links: list[dict] = Field(default_factory=list)
