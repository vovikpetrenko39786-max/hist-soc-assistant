import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1)
    mode: Literal["hybrid", "lexical", "vector", "exact"] = "hybrid"
    subject: str | None = None
    grade: int | None = Field(default=None, ge=1, le=11)
    level: str | None = None
    topic_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    source_key: str | None = None
    strict_source: bool = False
    source_statuses: list[str] = Field(
        default_factory=lambda: [
            "official", "primary", "exam", "secondary", "methodical", "reference"
        ]
    )
    include_archived: bool = False
    exact_phrase: str | None = None
    top_k: int = Field(default=8, ge=1, le=50)
    candidate_k: int = Field(default=40, ge=5, le=200)

    @model_validator(mode="after")
    def validate_scope(self):
        if self.strict_source and not (self.source_id or self.source_key):
            raise ValueError("strict_source=true requires source_id or source_key")
        if self.mode == "exact" and not self.exact_phrase:
            self.exact_phrase = self.query
        return self


class RetrievalHit(BaseModel):
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    source_key: str | None = None
    source_title: str
    source_type: str
    source_status: str
    origin: str | None = None
    authority_rank: int
    is_current: bool
    section: str | None = None
    page_pdf_start: int | None = None
    page_pdf_end: int | None = None
    page_print_start: int | None = None
    page_print_end: int | None = None
    snippet: str
    exact_match: bool = False
    quote_safe: bool = False
    lexical_rank: int | None = None
    vector_rank: int | None = None
    lexical_score: float | None = None
    vector_similarity: float | None = None
    final_score: float
    embedding_model: str | None = None
    page_reference_status: str


class RetrievalResponse(BaseModel):
    query: str
    mode: str
    strict_source: bool
    hits: list[RetrievalHit]
    warnings: list[str] = Field(default_factory=list)


class SourceEmbeddingOut(BaseModel):
    source_id: str
    source_key: str | None = None
    provider: str
    model: str
    dim: int
    chunks_total: int
    chunks_embedded: int
    chunks_ready: int
    source_status: str
    production_quality: bool
