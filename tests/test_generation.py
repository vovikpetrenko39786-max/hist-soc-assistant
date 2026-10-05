import asyncio
import uuid

from app.schemas.generation import LessonArtifact, LessonGenerationRequest
from app.services.generation_context import GroundedContextBuilder
from app.services.llm_provider import TemplateLessonProvider
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
