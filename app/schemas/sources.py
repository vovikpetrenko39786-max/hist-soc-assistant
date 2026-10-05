import uuid
from pydantic import BaseModel, Field

class SourceCatalogOut(BaseModel):
    id: uuid.UUID
    source_key: str | None = None
    title: str
    author: str | None = None
    subject: str | None = None
    grade: int | None = None
    level: str | None = None
    year: int | None = None
    publisher: str | None = None
    source_type: str
    status: str
    fpu_number: str | None = None
    isbn: str | None = None
    source_url: str | None = None
    authority_rank: int = 50
    verification_status: str | None = None
    rollout_status: str | None = None
    availability_status: str | None = None
    ingestion_status: str | None = None
    page_count: int | None = None
    has_text_layer: bool = False
    text_char_count: int | None = None
    coverage: str | None = None

class SourceResolveRequest(BaseModel):
    subject: str
    grade: int = Field(ge=1, le=11)
    level: str = 'basic'
    unit_title: str | None = None
    topic_title: str | None = None

class SourceResolveResult(BaseModel):
    source_key: str
    title: str
    source_role: str
    priority: int
    authority_rank: int
    verification_status: str | None = None
    rollout_status: str | None = None
    availability_status: str | None = None
    rationale: str


class SourceIngestionOut(BaseModel):
    source_id: str
    source_key: str | None = None
    title: str
    availability_status: str | None = None
    ingestion_status: str | None = None
    file_hash: str | None = None
    page_count: int | None = None
    has_text_layer: bool = False
    text_char_count: int | None = None
    run_id: str
    status: str
    original_filename: str | None = None
    file_size_bytes: int | None = None
    pages_with_text: int | None = None
    sections_created: int = 0
    chunks_created: int = 0
    needs_ocr: bool = False
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class SourceIngestionStatusOut(BaseModel):
    source_id: str
    source_key: str | None = None
    title: str
    availability_status: str | None = None
    ingestion_status: str | None = None
    file_path: str | None = None
    file_hash: str | None = None
    page_count: int | None = None
    has_text_layer: bool = False
    text_char_count: int | None = None
    latest_run: dict | None = None
