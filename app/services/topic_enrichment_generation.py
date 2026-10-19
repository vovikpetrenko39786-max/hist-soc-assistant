from __future__ import annotations

import re

from collections.abc import Mapping
from typing import Any, Protocol

from app.schemas.generation import TopicEnrichmentArtifact


class TopicEnrichmentGenerationError(RuntimeError):
    pass


class TopicEnrichmentProvider(Protocol):
    async def generate_topic_enrichment(self, context: dict) -> dict:
        ...


_MATERIAL_DEPENDENCY_PATTERN = re.compile(
    r"\b(?:"
    r"карт(?:а|ы|у|е|ой|ами|ах)?|"
    r"источник\w*|"
    r"документ\w*|"
    r"статистик\w*|"
    r"диаграм\w*|"
    r"иллюстрац\w*|"
    r"фотограф\w*|"
    r"цитат\w*|"
    r"отрывок\w*"
    r")\b",
    re.IGNORECASE,
)


def _normalize_label(value: str | None) -> str:
    return " ".join(
        re.sub(
            r"[^\w]+",
            " ",
            value or "",
            flags=re.UNICODE,
        ).casefold().split()
    )


def _validate_generated_artifact(
    artifact: TopicEnrichmentArtifact,
    context: Mapping[str, Any],
) -> None:
    concept_labels = {
        _normalize_label(item.get("term"))
        for item in (context.get("key_concepts") or [])
        if item.get("term")
    }
    example_labels = [
        _normalize_label(item.title)
        for item in artifact.common_examples
        if item.title
    ]

    if (
        example_labels
        and concept_labels
        and all(label in concept_labels for label in example_labels)
    ):
        raise TopicEnrichmentGenerationError(
            "Generated common examples only restate key concepts."
        )

    if not context.get("available_materials"):
        for activity in artifact.suitable_activities:
            activity_text = " ".join(
                [
                    activity.activity,
                    activity.purpose,
                    activity.student_action,
                ]
            )
            match = _MATERIAL_DEPENDENCY_PATTERN.search(
                activity_text
            )
            if match:
                raise TopicEnrichmentGenerationError(
                    "Generated activity depends on unavailable "
                    f"learning material: {match.group(0)}"
                )


def build_topic_enrichment_context(
    card: Mapping[str, Any],
) -> dict[str, Any]:
    subject = card.get("subject") or {}
    topic = card.get("topic") or {}

    concepts = (
        card.get("key_concepts")
        or card.get("concepts")
        or []
    )
    outcomes = (
        card.get("learning_outcomes")
        or card.get("outcomes")
        or []
    )
    skills = card.get("skills") or []
    available_materials = [
        item
        for item in (card.get("available_materials") or [])
        if isinstance(item, Mapping)
    ]

    official_sources = [
        source
        for source in (card.get("source_references") or [])
        if source.get("source_role") == "official_program"
    ]

    if not subject.get("code"):
        raise TopicEnrichmentGenerationError(
            "Topic Card has no subject code."
        )

    if not topic.get("title"):
        raise TopicEnrichmentGenerationError(
            "Topic Card has no topic title."
        )

    if not concepts:
        raise TopicEnrichmentGenerationError(
            "Topic Card has no key concepts."
        )

    if not outcomes:
        raise TopicEnrichmentGenerationError(
            "Topic Card has no learning outcomes."
        )

    if not official_sources:
        raise TopicEnrichmentGenerationError(
            "Topic Card has no official program source."
        )

    return {
        "subject": {
            "code": subject.get("code"),
            "name": subject.get("name"),
        },
        "grade": card.get("grade"),
        "level": card.get("level"),
        "topic": {
            "title": topic.get("title"),
            "description": topic.get("description"),
        },
        "key_concepts": [
            {
                "term": item.get("term"),
                "importance": item.get("importance"),
            }
            for item in concepts
        ],
        "learning_outcomes": [
            {
                "type": item.get("type"),
                "subtype": item.get("subtype"),
                "text": item.get("text"),
                "priority": item.get("priority"),
            }
            for item in outcomes
        ],
        "skills": [
            {
                "code": item.get("code"),
                "name": item.get("name"),
                "category": item.get("category"),
                "priority": item.get("priority"),
            }
            for item in skills
        ],
        "available_materials": [
            {
                "type": item.get("type"),
                "title": item.get("title"),
                "description": item.get("description"),
            }
            for item in available_materials
        ],
        "official_sources": [
            {
                "title": item.get("title"),
                "section": item.get("section"),
                "source_role": item.get("source_role"),
            }
            for item in official_sources
        ],
    }


class TopicEnrichmentGenerationService:
    def __init__(self, provider: TopicEnrichmentProvider):
        self.provider = provider

    async def generate(
        self,
        card: Mapping[str, Any],
    ) -> TopicEnrichmentArtifact:
        context = build_topic_enrichment_context(card)

        raw = await self.provider.generate_topic_enrichment(context)

        artifact = TopicEnrichmentArtifact.model_validate(raw)
        _validate_generated_artifact(artifact, context)

        return artifact
