from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from app.schemas.generation import TopicEnrichmentArtifact


class TopicEnrichmentGenerationError(RuntimeError):
    pass


class TopicEnrichmentProvider(Protocol):
    async def generate_topic_enrichment(self, context: dict) -> dict:
        ...


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

        return TopicEnrichmentArtifact.model_validate(raw)
