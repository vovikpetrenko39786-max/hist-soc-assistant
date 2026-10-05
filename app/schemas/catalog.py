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
    curriculum: dict
    unit: dict
    topic: dict
    outcomes: list[dict] = Field(default_factory=list)
    concepts: list[dict] = Field(default_factory=list)
    skills: list[dict] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    interdisciplinary_links: list[dict] = Field(default_factory=list)
    exam_links: list[dict] = Field(default_factory=list)
