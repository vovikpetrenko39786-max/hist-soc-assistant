import asyncio

import pytest

from app.services.topic_enrichment_generation import (
    TopicEnrichmentGenerationError,
    TopicEnrichmentGenerationService,
    build_topic_enrichment_context,
)


def topic_card():
    return {
        "subject": {
            "code": "HISTORY",
            "name": "История",
        },
        "grade": 10,
        "level": "basic",
        "topic": {
            "title": "Мировой экономический кризис",
            "description": None,
        },
        "key_concepts": [
            {
                "term": "Великая депрессия",
                "importance": "required",
                "definition_reference": "must-not-leak",
            }
        ],
        "learning_outcomes": [
            {
                "type": "subject",
                "subtype": "causality",
                "text": "Устанавливать причины и последствия кризиса.",
                "priority": 1,
                "source_reference": "must-not-leak",
            }
        ],
        "skills": [
            {
                "code": "establish_causality",
                "name": "Устанавливать причинно-следственные связи",
                "category": "cognitive",
                "priority": 1,
            }
        ],
        "source_references": [
            {
                "title": "Федеральная рабочая программа",
                "url": "https://example.test/official.pdf",
                "section": "Всеобщая история",
                "source_role": "official_program",
            },
            {
                "title": "Экзаменационный источник",
                "url": "https://example.test/exam",
                "source_role": "exam",
            },
        ],
        "content_summary": "Existing generated text must not feed itself.",
        "essential_questions": ["Existing generated question."],
        "provenance": {
            "content_summary": {
                "origin": "generated_candidate",
            }
        },
    }


def test_context_contains_only_allowed_topic_evidence():
    context = build_topic_enrichment_context(topic_card())

    assert context["subject"]["code"] == "HISTORY"
    assert context["grade"] == 10
    assert context["topic"]["title"] == "Мировой экономический кризис"

    assert context["key_concepts"] == [
        {
            "term": "Великая депрессия",
            "importance": "required",
        }
    ]

    assert context["official_sources"] == [
        {
            "title": "Федеральная рабочая программа",
            "section": "Всеобщая история",
            "source_role": "official_program",
        }
    ]

    assert "provenance" not in context
    assert "content_summary" not in context
    assert "essential_questions" not in context
    assert "exam_links" not in context

    assert "url" not in context["official_sources"][0]
    assert "definition_reference" not in context["key_concepts"][0]
    assert (
        "source_reference"
        not in context["learning_outcomes"][0]
    )


def test_service_generates_and_validates_artifact():
    captured = {}

    class FakeProvider:
        async def generate_topic_enrichment(self, context):
            captured["context"] = context
            return {
                "content_summary": (
                    "Кризис рассматривается через причины, "
                    "проявления и последствия."
                ),
                "common_examples": [
                    {
                        "title": "Безработица",
                        "description": (
                            "Рост безработицы показывает "
                            "социальные последствия кризиса."
                        ),
                    }
                ],
                "counterexamples": [
                    {
                        "title": "Одна причина",
                        "description": (
                            "Сведение кризиса к одному событию "
                            "искажает причинность."
                        ),
                    }
                ],
                "typical_misconceptions": [
                    "Биржевой крах считают единственной причиной."
                ],
                "essential_questions": [
                    "Почему кризис нельзя объяснить одной причиной?"
                ],
                "suitable_activities": [
                    {
                        "activity": "causality_chain",
                        "purpose": "Различить причины и последствия.",
                        "student_action": (
                            "Построить причинно-следственную цепочку."
                        ),
                    }
                ],
            }

    artifact = asyncio.run(
        TopicEnrichmentGenerationService(
            FakeProvider()
        ).generate(topic_card())
    )

    assert artifact.content_summary.startswith("Кризис")
    assert artifact.common_examples[0].title == "Безработица"
    assert captured["context"]["subject"]["code"] == "HISTORY"


def test_context_rejects_topic_without_official_evidence():
    card = topic_card()
    card["source_references"] = []

    with pytest.raises(
        TopicEnrichmentGenerationError,
        match="official program source",
    ):
        build_topic_enrichment_context(card)
