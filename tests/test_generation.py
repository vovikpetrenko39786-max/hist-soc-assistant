import asyncio
import uuid

from app.schemas.generation import LessonArtifact, LessonGenerationRequest
from app.services.generation_context import GroundedContextBuilder
from app.services.llm_provider import HttpLessonProvider, TemplateLessonProvider
from app.services.quality_gate import LessonQualityGate


def topic_card():
    return {
        "subject": {"id": str(uuid.uuid4()), "code": "SOCIAL_STUDIES", "name": "Обществознание"},
        "grade": 10,
        "curriculum": {
            "id": str(uuid.uuid4()),
            "title": "Обществознание 10",
            "level": "basic",
            "version": "2026",
            "status": "current",
            "review_status": "reviewed",
        },
        "unit": {
            "id": str(uuid.uuid4()),
            "title": "Человек и общество",
            "order_index": 1,
            "recommended_hours": 10,
        },
        "topic": {
            "id": str(uuid.uuid4()),
            "title": "Социальные институты",
            "aliases": [],
            "order_index": 3,
            "recommended_hours": 1,
            "topic_type": "new_content",
            "description": "",
            "default_lesson_blueprint": {},
            "typical_misconceptions": [
                "Смешение социального института и конкретной организации."
            ],
            "common_examples": [],
            "counterexamples": [],
            "essential_questions": [
                "Почему обществу нужны устойчивые социальные институты?"
            ],
            "reflection_patterns": [],
            "assessment_skills": [],
            "difficulty_level": 3,
            "abstraction_level": 4,
            "prerequisite_topic_ids": [],
            "review_status": "reviewed",
        },
        "outcomes": [
            {
                "id": str(uuid.uuid4()),
                "type": "subject",
                "subtype": None,
                "text": "Характеризовать социальные институты и объяснять их функции.",
                "source_reference": "FRP",
                "priority": 1,
            }
        ],
        "concepts": [
            {
                "id": str(uuid.uuid4()),
                "term": "социальный институт",
                "importance": "required",
                "definition_reference": None,
            },
            {
                "id": str(uuid.uuid4()),
                "term": "функции социального института",
                "importance": "required",
                "definition_reference": None,
            },
        ],
        "skills": [],
        "sources": [],
        "interdisciplinary_links": [],
        "exam_links": [],
    }


def retrieval():
    chunk_id = uuid.uuid4()
    source_id = uuid.uuid4()
    return {
        "query": "Социальные институты",
        "mode": "hybrid",
        "strict_source": False,
        "hits": [
            {
                "chunk_id": chunk_id,
                "source_id": source_id,
                "source_key": "TEST_BOOK",
                "source_title": "Учебник",
                "source_type": "textbook",
                "source_status": "primary",
                "origin": "teacher_upload",
                "authority_rank": 90,
                "is_current": True,
                "section": "§ 3",
                "page_pdf_start": 20,
                "page_pdf_end": 20,
                "page_print_start": 18,
                "page_print_end": 18,
                "snippet": "Социальные институты выполняют общественно значимые функции.",
                "exact_match": False,
                "quote_safe": False,
                "lexical_rank": 1,
                "vector_rank": 1,
                "lexical_score": 0.5,
                "vector_similarity": 0.8,
                "final_score": 0.9,
                "embedding_model": "hash-384-v1",
                "page_reference_status": "verified_print_and_pdf",
            }
        ],
        "warnings": [],
    }


def request():
    return LessonGenerationRequest(
        subject="SOCIAL_STUDIES",
        grade=10,
        level="basic",
        topic="Социальные институты",
        duration_minutes=45,
    )


def test_context_contains_grounding_contract_and_runtime_sop():
    context = GroundedContextBuilder().build_lesson_context(
        request(), topic_card(), retrieval()
    )
    assert context["source_manifest"]
    assert context["runtime_sop"]
    assert context["grounding_contract"]
    assert context["topic_card"]["topic"]["title"] == "Социальные институты"


def test_template_provider_returns_valid_artifact():
    context = GroundedContextBuilder().build_lesson_context(
        request(), topic_card(), retrieval()
    )
    raw = asyncio.run(TemplateLessonProvider().generate_lesson(context))
    artifact = LessonArtifact.model_validate(raw)
    assert artifact.title == "Социальные институты"
    assert sum(x.minutes for x in artifact.timeline) == 45
    assert artifact.source_references


def test_quality_gate_passes_template_artifact():
    card = topic_card()
    context = GroundedContextBuilder().build_lesson_context(
        request(), card, retrieval()
    )
    artifact = LessonArtifact.model_validate(
        asyncio.run(TemplateLessonProvider().generate_lesson(context))
    )
    report = LessonQualityGate().evaluate(
        artifact, card, context["source_manifest"]
    )
    assert report["passed"] is True
    assert report["score"] >= 80


def test_quality_gate_rejects_invented_source():
    card = topic_card()
    context = GroundedContextBuilder().build_lesson_context(
        request(), card, retrieval()
    )
    artifact = LessonArtifact.model_validate(
        asyncio.run(TemplateLessonProvider().generate_lesson(context))
    )
    artifact.source_references[0].chunk_id = uuid.uuid4()
    report = LessonQualityGate().evaluate(
        artifact, card, context["source_manifest"]
    )
    assert report["passed"] is False
    assert any(
        x["code"] == "source_subset" and not x["passed"]
        for x in report["checks"]
    )


def test_request_requires_topic():
    try:
        LessonGenerationRequest(subject="HISTORY", grade=6)
        assert False, "validation should fail"
    except Exception:
        pass


def test_http_provider_uses_strict_lesson_artifact_schema():
    schema = HttpLessonProvider._lesson_artifact_schema()

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])

    # Regression: the real LLM previously returned objects here,
    # while LessonArtifact requires lists of strings.
    assert schema["properties"]["key_concepts"]["items"]["type"] == "string"
    assert schema["properties"]["differentiation"]["items"]["type"] == "string"

    timeline = schema["$defs"]["LessonTimelineStep"]
    assert timeline["additionalProperties"] is False
    assert set(timeline["required"]) == set(timeline["properties"])

    source_reference = schema["$defs"]["SourceReference"]
    assert source_reference["additionalProperties"] is False
    assert set(source_reference["required"]) == set(source_reference["properties"])


def test_quality_gate_accepts_concepts_with_definitions():
    card = topic_card()
    context = GroundedContextBuilder().build_lesson_context(
        request(), card, retrieval()
    )

    raw = asyncio.run(TemplateLessonProvider().generate_lesson(context))
    artifact = LessonArtifact.model_validate(raw)

    required_terms = [
        item["term"]
        for item in card["concepts"]
        if item.get("importance") == "required"
    ]
    artifact.key_concepts = [
        f"{term} — содержательное определение для проверки."
        for term in required_terms
    ]

    report = LessonQualityGate().evaluate(
        artifact, card, context["source_manifest"]
    )

    check = next(
        x for x in report["checks"]
        if x["code"] == "required_concepts"
    )

    assert check["passed"] is True
    assert "100%" in check["message"]


def test_source_reference_metadata_is_grounded_from_manifest():
    from app.services.grounded_generation import _ground_source_references

    card = topic_card()
    context = GroundedContextBuilder().build_lesson_context(
        request(), card, retrieval()
    )
    artifact = LessonArtifact.model_validate(
        asyncio.run(TemplateLessonProvider().generate_lesson(context))
    )

    ref = artifact.source_references[0]
    manifest = next(
        item
        for item in context["source_manifest"]
        if str(item["chunk_id"]) == str(ref.chunk_id)
    )

    # Regression: a real LLM swapped page_pdf_end between two chunks
    # from the same official document.
    ref.source_id = "invented-source-id"
    ref.title = "Invented title"
    ref.url = "https://example.invalid/wrong"
    ref.section = "wrong section"
    ref.page_pdf_start = 999
    ref.page_pdf_end = 1000
    ref.page_print_start = 999
    ref.page_print_end = 1000
    ref.quote_safe = not bool(manifest.get("quote_safe", False))

    _ground_source_references(
        artifact,
        context["source_manifest"],
    )

    assert ref.source_id == str(manifest["source_id"])
    assert ref.source_key == manifest.get("source_key")
    assert ref.title == (
        manifest.get("title")
        or manifest.get("source_title")
    )
    assert ref.url == manifest.get("url")
    assert ref.section == manifest.get("section")
    assert ref.page_pdf_start == manifest.get("page_pdf_start")
    assert ref.page_pdf_end == manifest.get("page_pdf_end")
    assert ref.page_print_start == manifest.get("page_print_start")
    assert ref.page_print_end == manifest.get("page_print_end")
    assert ref.quote_safe == bool(manifest.get("quote_safe", False))

    report = LessonQualityGate().evaluate(
        artifact,
        card,
        context["source_manifest"],
    )
    page_check = next(
        x for x in report["checks"]
        if x["code"] == "page_grounding"
    )
    assert page_check["passed"] is True

    # Security regression: canonicalization must not hide an invented chunk.
    ref.chunk_id = str(uuid.uuid4())
    _ground_source_references(
        artifact,
        context["source_manifest"],
    )

    report = LessonQualityGate().evaluate(
        artifact,
        card,
        context["source_manifest"],
    )
    subset_check = next(
        x for x in report["checks"]
        if x["code"] == "source_subset"
    )
    assert subset_check["passed"] is False
