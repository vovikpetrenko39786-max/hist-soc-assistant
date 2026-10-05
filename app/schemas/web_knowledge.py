from typing import Literal
from pydantic import BaseModel, Field


class WebKnowledgeRequest(BaseModel):
    query: str = Field(min_length=1, max_length=12000)
    subject: str | None = None
    grade: int | None = Field(default=None, ge=1, le=11)
    policy: Literal["library_only", "library_first", "official_web_first"] = "library_first"
    scope: Literal["official", "general"] = "official"
    force_search: bool = True


class WebSource(BaseModel):
    url: str
    title: str | None = None
    domain: str | None = None
    source_type: str = "web"


class WebKnowledgeResponse(BaseModel):
    performed: bool
    provider: str
    model: str | None = None
    policy: str
    scope: str
    query: str
    allowed_domains: list[str] = Field(default_factory=list)
    answer: str | None = None
    sources: list[WebSource] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)
    search_run_id: str | None = None
    warnings: list[str] = Field(default_factory=list)
