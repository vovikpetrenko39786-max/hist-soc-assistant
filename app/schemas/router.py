from typing import Literal

from pydantic import BaseModel


class RouterPreviewRequest(BaseModel):
    text: str


class RoutedRequest(BaseModel):
    task: Literal[
        "lesson",
        "assessment",
        "material",
        "homework",
        "memory_query",
        "source_query",
        "unknown",
    ]
    subject: Literal["history", "social_studies", "individual_project", "unknown"]
    grade: int | None = None
    class_label: str | None = None
    mode: Literal["short", "full", "emergency", "formal", "practical", "default"] = "default"
    strict_source: bool = False
