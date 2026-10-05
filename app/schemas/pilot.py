import uuid
from typing import Literal

from pydantic import BaseModel, Field


class PilotFeedbackCreate(BaseModel):
    category: Literal["feedback", "bug", "idea", "content_error"] = "feedback"
    channel: str = "telegram"
    user_external_id: str | None = None
    username: str | None = None
    display_name: str | None = None
    text: str = Field(min_length=1, max_length=12000)
    last_request: str | None = Field(default=None, max_length=12000)
    generation_run_id: uuid.UUID | None = None
    metadata: dict = Field(default_factory=dict)


class PilotFeedbackOut(BaseModel):
    id: uuid.UUID
    category: str
    channel: str
    username: str | None = None
    display_name: str | None = None
    text: str
    last_request: str | None = None
    generation_run_id: uuid.UUID | None = None
    status: str
    created_at: str


class PilotStatsOut(BaseModel):
    release: str
    feedback_total: int
    feedback_open: int
    generation_total: int
    generation_failed: int
    exports_total: int
