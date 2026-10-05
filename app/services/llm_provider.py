from __future__ import annotations

import json
from typing import Protocol

import httpx

from app.core.config import get_settings

settings = get_settings()


class GenerationProviderError(RuntimeError):
    pass


class GenerationProvider(Protocol):
    name: str
    model: str

    async def generate_lesson(self, context: dict) -> dict:
        ...


class TemplateLessonProvider:
    """Deterministic offline provider for tests and integration demos."""

    name = "template"

    def __init__(self, model: str = "template-lesson-v1"):
        self.model = model

    @staticmethod
    def _concepts(card: dict) -> list[str]:
        concepts = [
            item["term"] for item in card.get("concepts", [])
            if item.get("importance") == "required"
        ]
        return concepts[:6] or [item["term"] for item in card.get("concepts", [])[:6]]

    @staticmethod
    def _outcomes(card: dict) -> list[str]:
        subject = [
            item["text"] for item in card.get("outcomes", [])
            if item.get("type") == "subject"
        ]
        candidates = subject or [item["text"] for item in card.get("outcomes", [])]
        return candidates[:3]

    @staticmethod
    def _source_refs(manifest: list[dict]) -> list[dict]:
        return [
            {
                "chunk_id": item["chunk_id"],
                "source_id": item["source_id"],
                "source_key": item.get("source_key"),
                "title": item["title"],
                "section": item.get("section"),
                "page_pdf_start": item.get("page_pdf_start"),
                "page_pdf_end": item.get("page_pdf_end"),
                "page_print_start": item.get("page_print_start"),
                "page_print_end": item.get("page_print_end"),
                "quote_safe": item.get("quote_safe", False),
            }
            for item in manifest[:4]
        ]

    async def generate_lesson(self, context: dict) -> dict:
        card = context["topic_card"]
        topic = card["topic"]
        grade = card["grade"]
        subject = card["subject"]["code"]
        duration = int(context["duration_minutes"])
        concepts = self._concepts(card)
        outcomes = self._outcomes(card)

        if not outcomes:
            outcomes = [
                f"Объяснять содержание темы «{topic['title']}» и применять изученное в учебной ситуации."
            ]

        question = None
        if topic.get("essential_questions"):
            question = topic["essential_questions"][0]
        if not question:
            question = f"Почему тема «{topic['title']}» важна для понимания предмета?"

        # Realistic 45-min-like partition scaled for requested duration.
        base = [
            ("Вход и проблемный вопрос", 5),
            ("Актуализация", 6),
            ("Осмысление нового материала", 13),
            ("Применение", 12),
            ("Проверка понимания", 5),
            ("Рефлексия и следующий шаг", 4),
        ]
        total_base = sum(x[1] for x in base)
        minutes = [max(1, round(duration * value / total_base)) for _, value in base]
        # Correct rounding to exact duration.
        minutes[-1] += duration - sum(minutes)

        stages = [
            {
                "minutes": minutes[0],
                "stage": base[0][0],
                "teacher_action": f"Предъявляет вопрос: «{question}» и фиксирует первые версии.",
                "student_action": "Формулируют первоначальный ответ и называют, чего не хватает для доказательства.",
                "evidence_of_learning": "Есть исходная версия ответа, к которой можно вернуться в конце.",
            },
            {
                "minutes": minutes[1],
                "stage": base[1][0],
                "teacher_action": "Организует короткое задание на актуализацию необходимого предшествующего знания.",
                "student_action": "Восстанавливают ключевые факты/понятия и объясняют одну связь с новой темой.",
                "evidence_of_learning": "Ученик не просто называет факт, а связывает его с новой темой.",
            },
            {
                "minutes": minutes[2],
                "stage": base[2][0],
                "teacher_action": f"Выстраивает объяснение вокруг понятий: {', '.join(concepts[:4]) if concepts else topic['title']}.",
                "student_action": "Выделяют признаки/причины/связи, задают уточняющие вопросы и формулируют промежуточный вывод.",
                "evidence_of_learning": "Промежуточный вывод использует предметные понятия.",
            },
            {
                "minutes": minutes[3],
                "stage": base[3][0],
                "teacher_action": "Даёт задачу на применение нового содержания в новой ситуации, сравнении, кейсе или источнике.",
                "student_action": "Применяют изученное и объясняют ход решения, а не только называют ответ.",
                "evidence_of_learning": "Есть объяснение, пример или причинно-следственная связь.",
            },
            {
                "minutes": minutes[4],
                "stage": base[4][0],
                "teacher_action": "Проводит короткую индивидуальную проверку по ключевому результату урока.",
                "student_action": "Самостоятельно выполняют проверочное задание и сверяют критерий успеха.",
                "evidence_of_learning": outcomes[0],
            },
            {
                "minutes": minutes[5],
                "stage": base[5][0],
                "teacher_action": "Возвращает класс к исходному проблемному вопросу.",
                "student_action": "Уточняют первоначальный ответ: что теперь могут доказать точнее и почему.",
                "evidence_of_learning": "Финальный ответ содержательнее исходной версии.",
            },
        ]

        notebook = []
        if concepts:
            notebook.append("Ключевые понятия: " + ", ".join(concepts[:6]) + ".")
        notebook.append(
            f"Итоговый вывод по теме «{topic['title']}»: 2–3 смысловых пункта, сформулированных по итогам работы."
        )

        exam_perspective = []
        for link in card.get("exam_links", [])[:3]:
            exam = link.get("exam")
            section = link.get("exam_section")
            if exam:
                exam_perspective.append(
                    f"{exam}: связь с разделом/умением"
                    + (f" «{section}»" if section else "")
                    + "."
                )

        return {
            "title": topic["title"],
            "grade": grade,
            "subject": subject,
            "duration_minutes": duration,
            "essential_question": question,
            "goal": f"Создать условия, чтобы учащиеся осмысленно объясняли тему «{topic['title']}» и применяли изученное.",
            "measurable_outcomes": outcomes,
            "key_concepts": concepts,
            "timeline": stages,
            "notebook": notebook,
            "differentiation": [
                "Поддержка: дать опорные вопросы/частично заполненную схему без готового ответа.",
                "Усложнение: потребовать доказательство, контрпример, сравнение или перенос в новую ситуацию.",
            ],
            "formative_check": [
                f"Ученик должен продемонстрировать: {outcomes[0]}",
                "Проверка проводится индивидуально до общей сверки.",
            ],
            "reflection": [
                f"Вернитесь к вопросу: «{question}»",
                "Назовите одно уточнение или исправление в своём первоначальном ответе.",
            ],
            "homework": None,
            "reserve_task": "Сформулировать один собственный пример/вывод и объяснить, почему он соответствует теме.",
            "cut_first_if_short_on_time": [
                "Сократить дополнительное обсуждение примеров, но сохранить применение и проверку понимания."
            ],
            "exam_perspective": exam_perspective,
            "source_references": self._source_refs(context.get("source_manifest", [])),
        }


class HttpLessonProvider:
    """Generic chat-completions-style HTTP provider."""

    name = "http"

    def __init__(self):
        if not settings.generation_http_base_url:
            raise GenerationProviderError(
                "GENERATION_HTTP_BASE_URL is required for generation_provider=http"
            )
        self.base_url = settings.generation_http_base_url.rstrip("/")
        self.api_key = settings.generation_http_api_key
        self.model = settings.generation_http_model or settings.generation_model

    @staticmethod
    def _system_prompt() -> str:
        return (
            "Ты — генератор учебных материалов. Возвращай ТОЛЬКО JSON-объект, "
            "соответствующий схеме LessonArtifact. Не добавляй источники, chunk_id, "
            "source_id или страницы, которых нет в source_manifest. "
            "Не выдавай semantic snippets за дословные цитаты."
        )

    async def generate_lesson(self, context: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "temperature": settings.generation_temperature,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False, default=str),
                },
            ],
        }

        async with httpx.AsyncClient(
            timeout=settings.generation_http_timeout_seconds
        ) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise GenerationProviderError(
                    f"Generation endpoint returned {response.status_code}: "
                    f"{response.text[:600]}"
                ) from exc

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GenerationProviderError("Unexpected generation response shape") from exc

        if isinstance(content, dict):
            return content

        text = str(content).strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].lstrip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise GenerationProviderError(
                "Model did not return valid JSON LessonArtifact"
            ) from exc


def get_generation_provider() -> GenerationProvider:
    provider = settings.generation_provider.lower().strip()
    if provider == "template":
        return TemplateLessonProvider(settings.generation_model)
    if provider == "http":
        return HttpLessonProvider()
    raise GenerationProviderError(
        f"Unsupported generation provider: {settings.generation_provider}"
    )
