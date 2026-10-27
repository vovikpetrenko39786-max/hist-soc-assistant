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


def retrieval():
    return {
        "query": "Мировой экономический кризис",
        "mode": "hybrid",
        "strict_source": False,
        "warnings": [],
        "hits": [
            {
                "chunk_id": "11111111-1111-1111-1111-111111111111",
                "source_id": "22222222-2222-2222-2222-222222222222",
                "source_key": "history-source",
                "source_title": "История. Учебный источник",
                "url": "https://example.test/history.pdf",
                "source_status": "secondary",
                "section": "Мировой экономический кризис",
                "page_pdf_start": 10,
                "page_pdf_end": 10,
                "page_print_start": 8,
                "page_print_end": 8,
                "quote_safe": False,
                "snippet": (
                    "Великая депрессия сопровождалась "
                    "ростом безработицы и сокращением производства."
                ),
            }
        ],
    }


def test_context_contains_only_allowed_topic_evidence():
    context = build_topic_enrichment_context(topic_card(), retrieval())

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
    assert context["retrieved_evidence"][0]["snippet"].startswith(
        "Великая депрессия"
    )
    assert "url" not in context["retrieved_evidence"][0]
    assert "definition_reference" not in context["key_concepts"][0]
    assert (
        "source_reference"
        not in context["learning_outcomes"][0]
    )


def test_service_generates_and_validates_artifact():
    captured = {}

    class FakeProvider:
        async def review_topic_enrichment(self, context, artifact):
            return {"evidence_sufficient": True, "claims_grounded": True, "issues": [],
                    "activities": [{"activity_index": i, "answer_complete": True,
                                    "criteria_aligned": True, "issues": []}
                                   for i, _ in enumerate(artifact["suitable_activities"])]}

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
                        "expected_answer": "Сокращение производства и рост безработицы.",
                        "assessment_criteria": ["Названы оба проявления кризиса."],
                    }
                ],
            }

    artifact = asyncio.run(
        TopicEnrichmentGenerationService(
            FakeProvider()
        ).generate(topic_card(), retrieval())
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
        build_topic_enrichment_context(card, retrieval())


def test_service_rejects_examples_that_only_repeat_key_concepts():
    class FakeProvider:
        async def review_topic_enrichment(self, context, artifact):
            return {"evidence_sufficient": True, "claims_grounded": True, "issues": [],
                    "activities": [{"activity_index": i, "answer_complete": True,
                                    "criteria_aligned": True, "issues": []}
                                   for i, _ in enumerate(artifact["suitable_activities"])]}

        async def generate_topic_enrichment(self, context):
            return {
                "content_summary": "Summary",
                "common_examples": [
                    {
                        "title": "Великая депрессия",
                        "description": "Повтор понятия вместо примера.",
                    }
                ],
                "counterexamples": [],
                "typical_misconceptions": [],
                "essential_questions": [],
                "suitable_activities": [],
            }

    with pytest.raises(
        TopicEnrichmentGenerationError,
        match="only restate key concepts",
    ):
        asyncio.run(
            TopicEnrichmentGenerationService(
                FakeProvider()
            ).generate(topic_card(), retrieval())
        )


def test_service_rejects_unavailable_learning_material():
    class FakeProvider:
        async def review_topic_enrichment(self, context, artifact):
            return {"evidence_sufficient": True, "claims_grounded": True, "issues": [],
                    "activities": [{"activity_index": i, "answer_complete": True,
                                    "criteria_aligned": True, "issues": []}
                                   for i, _ in enumerate(artifact["suitable_activities"])]}

        async def generate_topic_enrichment(self, context):
            return {
                "content_summary": "Summary",
                "common_examples": [
                    {
                        "title": "Безработица",
                        "description": "Конкретное проявление кризиса.",
                    }
                ],
                "counterexamples": [],
                "typical_misconceptions": [],
                "essential_questions": [],
                "suitable_activities": [
                    {
                        "activity": "Разобрать карту по теме.",
                        "purpose": "Извлечь сведения из карты.",
                        "student_action": "Проанализировать карту.",
                    }
                ],
            }

    with pytest.raises(
        TopicEnrichmentGenerationError,
        match="unavailable learning material",
    ):
        asyncio.run(
            TopicEnrichmentGenerationService(
                FakeProvider()
            ).generate(topic_card(), retrieval())
        )



def test_context_rejects_missing_retrieved_evidence():
    with pytest.raises(
        TopicEnrichmentGenerationError,
        match="requires retrieved evidence",
    ):
        build_topic_enrichment_context(
            topic_card(),
            {"hits": []},
        )



def test_context_filters_single_concept_retrieval_noise():
    card = topic_card()
    card["key_concepts"] = [
        {
            "term": "мировой экономический кризис",
            "importance": "required",
        },
        {
            "term": "Великая депрессия",
            "importance": "required",
        },
        {
            "term": "Новый курс Ф. Д. Рузвельта",
            "importance": "required",
        },
    ]

    base_hit = retrieval()["hits"][0]

    relevant_hit = {
        **base_hit,
        "chunk_id": "33333333-3333-3333-3333-333333333333",
        "snippet": (
            "Мировой экономический кризис 1929–1933 гг. "
            "и начало Великой депрессии. "
            "Новый курс Ф. Д. Рузвельта."
        ),
    }

    noise_hit = {
        **base_hit,
        "chunk_id": "44444444-4444-4444-4444-444444444444",
        "page_pdf_start": 101,
        "page_pdf_end": 102,
        "snippet": (
            "Мировой экономический кризис 2008 г. "
            "Социальная политика и занятость населения."
        ),
    }

    context = build_topic_enrichment_context(
        card,
        {
            "hits": [
                noise_hit,
                relevant_hit,
            ]
        },
    )

    assert len(context["retrieved_evidence"]) == 1
    assert (
        context["retrieved_evidence"][0]["chunk_id"]
        == relevant_hit["chunk_id"]
    )
    assert (
        "2008"
        not in context["retrieved_evidence"][0]["snippet"]
    )


@pytest.mark.parametrize(
    "bad_text, expected_split",
    [
        ("процессы имеры", "имеры -> и + меры"),
        (
            "экономическийкризис",
            "экономическийкризис -> экономический + кризис",
        ),
        (
            "последствиямикризиса",
            "последствиямикризиса -> последствиями + кризиса",
        ),
        (
            "чтобиржевой",
            "чтобиржевой -> что + биржевой",
        ),
        (
            "затемсформулировать",
            "затемсформулировать -> затем + сформулировать",
        ),
    ],
)
def test_service_rejects_suspicious_joined_russian_words(
    bad_text,
    expected_split,
):
    class FakeProvider:
        async def review_topic_enrichment(self, context, artifact):
            return {"evidence_sufficient": True, "claims_grounded": True, "issues": [],
                    "activities": [{"activity_index": i, "answer_complete": True,
                                    "criteria_aligned": True, "issues": []}
                                   for i, _ in enumerate(artifact["suitable_activities"])]}

        async def generate_topic_enrichment(self, context):
            return {
                "content_summary": bad_text,
                "common_examples": [
                    {
                        "title": "Безработица",
                        "description": "Проявление экономического кризиса.",
                    }
                ],
                "counterexamples": [],
                "typical_misconceptions": [],
                "essential_questions": [],
                "suitable_activities": [],
            }

    with pytest.raises(
        TopicEnrichmentGenerationError,
        match="suspicious joined word",
    ) as exc_info:
        asyncio.run(
            TopicEnrichmentGenerationService(
                FakeProvider()
            ).generate(
                topic_card(),
                retrieval(),
            )
        )

    assert expected_split in str(exc_info.value)


def test_service_accepts_normal_russian_words():
    class FakeProvider:
        async def review_topic_enrichment(self, context, artifact):
            return {"evidence_sufficient": True, "claims_grounded": True, "issues": [],
                    "activities": [{"activity_index": i, "answer_complete": True,
                                    "criteria_aligned": True, "issues": []}
                                   for i, _ in enumerate(artifact["suitable_activities"])]}

        async def generate_topic_enrichment(self, context):
            return {
                "content_summary": (
                    "Экономический кризис имел серьёзные последствия."
                ),
                "common_examples": [
                    {
                        "title": "Безработица",
                        "description": (
                            "Последствиями кризиса стали "
                            "социальные трудности."
                        ),
                    }
                ],
                "counterexamples": [],
                "typical_misconceptions": [
                    "Биржевой крах нельзя считать единственной причиной."
                ],
                "essential_questions": [
                    "Как сформулировать исторически обоснованный вывод?"
                ],
                "suitable_activities": [],
            }

    artifact = asyncio.run(
        TopicEnrichmentGenerationService(
            FakeProvider()
        ).generate(
            topic_card(),
            retrieval(),
        )
    )

    assert artifact.content_summary.startswith(
        "Экономический кризис"
    )


def guided_artifact():
    return {
        "content_summary": "Кризис сопровождался сокращением производства и ростом безработицы.",
        "common_examples": [{"title": "Безработица", "description": "Рост безработицы."}],
        "counterexamples": [],
        "typical_misconceptions": [],
        "essential_questions": [],
        "suitable_activities": [{
            "activity": "Проявления кризиса",
            "purpose": "Назвать проявления кризиса.",
            "student_action": "Назовите два проявления кризиса.",
            "expected_answer": "Сокращение производства и рост безработицы.",
            "assessment_criteria": ["Названо сокращение производства.", "Назван рост безработицы."],
        }],
    }


def generate_payload(payload):
    class FakeProvider:
        async def review_topic_enrichment(self, context, artifact):
            return {"evidence_sufficient": True, "claims_grounded": True, "issues": [],
                    "activities": [{"activity_index": i, "answer_complete": True,
                                    "criteria_aligned": True, "issues": []}
                                   for i, _ in enumerate(artifact["suitable_activities"])]}

        async def generate_topic_enrichment(self, context):
            return payload

    return asyncio.run(
        TopicEnrichmentGenerationService(FakeProvider()).generate(topic_card(), retrieval())
    )


@pytest.mark.parametrize("field", ["expected_answer", "assessment_criteria"])
def test_new_generation_rejects_missing_teacher_guidance(field):
    payload = guided_artifact()
    del payload["suitable_activities"][0][field]
    with pytest.raises(TopicEnrichmentGenerationError, match="requires"):
        generate_payload(payload)


@pytest.mark.parametrize("field,value", [
    ("expected_answer", None),
    ("expected_answer", ""),
    ("expected_answer", "   "),
    ("assessment_criteria", None),
    ("assessment_criteria", []),
    ("assessment_criteria", ["  "]),
    ("assessment_criteria", ["Есть ответ.", ""]),
])
def test_new_generation_rejects_empty_teacher_guidance(field, value):
    payload = guided_artifact()
    payload["suitable_activities"][0][field] = value
    with pytest.raises(TopicEnrichmentGenerationError, match="requires"):
        generate_payload(payload)


def test_teacher_guidance_survives_generation_and_json_round_trip():
    from app.schemas.generation import TopicEnrichmentArtifact

    payload = guided_artifact()
    artifact = generate_payload(payload)
    restored = TopicEnrichmentArtifact.model_validate_json(artifact.model_dump_json())
    assert restored.model_dump(mode="json") == payload


@pytest.mark.parametrize("legacy", [True, False])
def test_saved_candidate_guidance_round_trip_preserves_hash(tmp_path, legacy):
    from uuid import UUID
    from app.schemas.generation import TopicEnrichmentArtifact
    import scripts.enrich_topic_card as script

    payload = guided_artifact()
    if legacy:
        del payload["suitable_activities"][0]["expected_answer"]
        del payload["suitable_activities"][0]["assessment_criteria"]
    artifact = TopicEnrichmentArtifact.model_validate(payload)
    assert artifact.model_dump(mode="python") == payload
    assert artifact.model_dump(mode="json") == payload
    assert script.json.loads(artifact.model_dump_json()) == payload
    topic_id = UUID("3b5a578c-4352-4ca6-bd79-19d48aed5365")
    patch = {
        "suitable_activities": payload["suitable_activities"],
        "verification_status": "pending_review",
        "provenance": {"suitable_activities": {
            "origin": "generated_candidate",
            "status": "pending_review",
            "source_chunk_ids": ["evidence-1"],
        }},
    }
    candidate = script._build_candidate(
        topic_id=topic_id,
        topic_card_hash="0" * 64,
        artifact=payload,
        proposed_patch=patch,
        evidence_chunk_ids=["evidence-1"],
    )
    script._save_candidate(candidate, tmp_path)
    assert script._load_candidate(
        candidate_id=candidate["candidate_id"], topic_id=topic_id, candidate_dir=tmp_path,
    ) == candidate


def test_provider_schema_requests_teacher_guidance():
    from app.services.llm_provider import HttpLessonProvider

    schema = HttpLessonProvider._topic_enrichment_artifact_schema()
    activity = schema["$defs"]["TopicEnrichmentActivity"]
    assert {"expected_answer", "assessment_criteria"} <= set(activity["required"])
    assert activity["additionalProperties"] is False


def test_text_quality_check_covers_teacher_guidance():
    payload = guided_artifact()
    payload["suitable_activities"][0]["expected_answer"] = "экономическийкризис"
    with pytest.raises(TopicEnrichmentGenerationError, match="suspicious joined word"):
        generate_payload(payload)


@pytest.mark.parametrize("fault", ["evidence", "claims", "answer", "criteria", "issue", "missing", "duplicate", "unknown", "invalid", "unavailable"])
def test_semantic_review_blocks_bad_or_incomplete_review(fault):
    from pydantic import ValidationError
    from app.services.llm_provider import GenerationProviderError
    class Provider:
        async def generate_topic_enrichment(self, context):
            return guided_artifact()

        async def review_topic_enrichment(self, context, artifact):
            assert artifact == guided_artifact()
            assert context["retrieved_evidence"][0]["snippet"] == retrieval()["hits"][0]["snippet"]
            if fault == "unavailable":
                raise GenerationProviderError("review unavailable")
            result = {"evidence_sufficient": True, "claims_grounded": True, "issues": [],
                      "activities": [{"activity_index": 0, "answer_complete": True,
                                      "criteria_aligned": True, "issues": []}]}
            if fault == "evidence": result["evidence_sufficient"] = False
            if fault == "claims": result["claims_grounded"] = False
            if fault == "answer": result["activities"][0]["answer_complete"] = False
            if fault == "criteria": result["activities"][0]["criteria_aligned"] = False
            if fault == "issue": result["activities"][0]["issues"] = ["Missing requested example"]
            if fault == "missing": result["activities"] = []
            if fault == "duplicate": result["activities"] *= 2
            if fault == "unknown": result["activities"][0]["activity_index"] = 1
            if fault == "invalid": result["claims_grounded"] = "true"
            return result
    with pytest.raises((TopicEnrichmentGenerationError, ValidationError, GenerationProviderError)):
        asyncio.run(TopicEnrichmentGenerationService(Provider()).generate(topic_card(), retrieval()))


def test_generation_requires_review_capability():
    class Provider:
        async def generate_topic_enrichment(self, context):
            return guided_artifact()
    with pytest.raises(TopicEnrichmentGenerationError, match="review support"):
        asyncio.run(TopicEnrichmentGenerationService(Provider()).generate(topic_card(), retrieval()))
