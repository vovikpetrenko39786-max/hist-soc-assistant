import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator


OutputFormat = Literal["docx", "pdf"]
OutputAudience = Literal["teacher", "student"]


class OutputRenderRequest(BaseModel):
    generation_run_id: uuid.UUID | None = None
    artifact: dict | None = None
    artifact_type: str | None = None
    audience: OutputAudience = "teacher"
    formats: list[OutputFormat] = Field(default_factory=lambda: ["docx", "pdf"])
    template_name: str = "school_clean"
    filename_base: str | None = None

    @model_validator(mode="after")
    def validate_source(self):
        if not self.generation_run_id and not self.artifact:
            raise ValueError("generation_run_id or artifact is required")
        if self.generation_run_id and self.artifact:
            raise ValueError("provide generation_run_id or artifact, not both")
        if not self.formats:
            raise ValueError("at least one output format is required")
        return self


class OutputFileInfo(BaseModel):
    export_id: uuid.UUID | None = None
    file_name: str
    file_format: OutputFormat
    audience: OutputAudience
    template_name: str
    template_version: str
    size_bytes: int
    sha256: str
    file_path: str
    download_path: str | None = None


class OutputRenderResponse(BaseModel):
    artifact_type: str
    audience: OutputAudience
    files: list[OutputFileInfo]
    warnings: list[str] = Field(default_factory=list)
