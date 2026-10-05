from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.pedagogy import (
    AssessmentArtifact,
    HomeworkArtifact,
    IdeaEnhancementArtifact,
    LessonArtifact,
    WorksheetArtifact,
)
from app.services.llm_provider import GenerationProviderError
from app.services.pedagogy_provider import source_refs

settings = get_settings()


_ARTIFACT_MODELS = {
    "lesson": LessonArtifact,
    "assessment": AssessmentArtifact,
    "worksheet": WorksheetArtifact,
    "homework": HomeworkArtifact,
    "idea_enhancement": IdeaEnhancementArtifact,
}


def _extract_output_text(payload: dict) -> str:
    if payload.get("output_text"):
        return str(payload["output_text"])
    parts = []
    for item in payload.get("output", []) or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []) or []:
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(str(content["text"]))
    return "\n".join(parts).strip()


def _student_from_teacher(artifact_type: str, teacher: dict) -> dict | None:
    if artifact_type in {"lesson", "idea_enhancement"}:
        return None

    student = deepcopy(teacher)

    if artifact_type == "assessment":
        for task in student.get("tasks", []):
            task["answer"] = None
            task["criteria"] = None
        student["common_errors_to_watch"] = []

    elif artifact_type == "worksheet":
        for section in student.get("sections", []):
            for task in section.get("tasks", []):
                task["answer"] = None
                task["criteria"] = None
        student["teacher_key"] = []

    elif artifact_type == "homework":
        student["teacher_note"] = None

    return student


class OpenAIResponsesPedagogyProvider:
    name = "openai_responses"

    def __init__(self):
        self.model = settings.openai_generation_model
        self.base_url = settings.openai_responses_base_url.rstrip("/")
        if not settings.openai_api_key:
            raise GenerationProviderError(
                "OPENAI_API_KEY is required for generation_provider=openai_responses"
            )

    @staticmethod
    def _schema(artifact_type: str) -> dict:
        model = _ARTIFACT_MODELS[artifact_type]
        schema = model.model_json_schema()
        # The model must not be responsible for evidence identifiers.
        # We replace source_references after validation anyway.
        return schema

    @staticmethod
    def _instructions(artifact_type: str) -> str:
        return (
            "Ты — педагогический генератор для российских учителей истории и обществознания. "
            "Создай только один teacher artifact указанного типа. "
            "Строго используй переданный Topic Card, runtime_sop и evidence context. "
            "Не выдумывай цитаты, страницы, параграфы, нормативные документы и экзаменационные факты. "
            "Если web_retrieval содержит актуальные сведения, используй их только как дополнительную доказательную базу. "
            "Не добавляй рекламных или лишних вводных фраз. "
            "Для assessment формулируй реальные предметные задания, полноценные ответы и конкретные критерии, "
            "а не заглушки вроде 'ответ проверяется по смыслу'. "
            "Для worksheet делай задания, пригодные для печати и самостоятельной работы ученика. "
            "Для lesson соблюдай реалистичный тайминг и связку результат→деятельность→проверка. "
            "source_references можешь оставить пустым: backend добавит проверенные ссылки сам."
        )

    async def _call(self, artifact_type: str, context: dict, correction: str | None = None) -> dict:
        schema = self._schema(artifact_type)
        user_payload = {
            "task": "Create a teacher-facing pedagogical artifact.",
            "artifact_type": artifact_type,
            "context": context,
        }
        if correction:
            user_payload["previous_validation_error"] = correction
            user_payload["instruction"] = "Correct the structure/content and return the artifact again."

        body = {
            "model": self.model,
            "store": False,
            "reasoning": {"effort": settings.openai_generation_reasoning_effort},
            "instructions": self._instructions(artifact_type),
            "input": json.dumps(user_payload, ensure_ascii=False, default=str),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": f"{artifact_type}_artifact",
                    "schema": schema,
                    "strict": False,
                }
            },
        }
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=settings.openai_generation_timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/responses",
                headers=headers,
                json=body,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise GenerationProviderError(
                    f"OpenAI Responses API returned {response.status_code}: {response.text[:800]}"
                ) from exc

        text = _extract_output_text(response.json())
        if not text:
            raise GenerationProviderError("OpenAI Responses API returned no output text")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise GenerationProviderError(
                f"OpenAI returned invalid JSON: {text[:500]}"
            ) from exc

    async def generate(self, context: dict) -> dict:
        artifact_type = context["artifact_type"]
        model_cls = _ARTIFACT_MODELS.get(artifact_type)
        if not model_cls:
            raise GenerationProviderError(f"Unsupported artifact type: {artifact_type}")

        error = None
        raw: dict[str, Any] | None = None
        attempts = max(1, settings.openai_generation_max_retries + 1)
        for _ in range(attempts):
            raw = await self._call(artifact_type, context, correction=error)
            # Evidence references are always backend-controlled.
            raw["source_references"] = source_refs(context.get("source_manifest", []))
            try:
                teacher_obj = model_cls.model_validate(raw)
                teacher = teacher_obj.model_dump(mode="json")
                student = _student_from_teacher(artifact_type, teacher)
                return {"teacher": teacher, "student": student}
            except ValidationError as exc:
                error = str(exc)

        raise GenerationProviderError(
            f"OpenAI artifact failed schema validation after {attempts} attempt(s): {error}"
        )
