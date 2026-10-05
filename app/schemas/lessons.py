import uuid
from datetime import date

from pydantic import BaseModel, Field


class LessonCreate(BaseModel):
    class_course_id: uuid.UUID
    date: date
    topic: str
    lesson_number: int | None = None
    lesson_type: str | None = None
    duration_minutes: int = Field(default=45, gt=0)
    planned_content: str | None = None


class LessonComplete(BaseModel):
    completed_content: str
    unfinished_content: str | None = None
    reflection: str | None = None
    next_step: str | None = None
    partial: bool = False
