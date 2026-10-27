"""Ephemeral review; never alters signed candidate serialization."""
from pydantic import BaseModel, ConfigDict, Field, StrictBool


class ActivityReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activity_index: int = Field(ge=0, strict=True)
    answer_complete: StrictBool
    criteria_aligned: StrictBool
    issues: list[str]


class TopicEnrichmentReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_sufficient: StrictBool
    claims_grounded: StrictBool
    issues: list[str]
    activities: list[ActivityReview]
