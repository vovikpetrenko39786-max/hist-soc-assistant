import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.schemas.catalog import TopicCardOut
from app.services.catalog import CurriculumCatalogService
from app.services.topic_card_enrichment import (
    apply_topic_card_enrichment,
    build_topic_card_enrichment,
)
from scripts.import_official_curricula import set_if_available, topic_card_provenance


DATASET = Path(__file__).resolve().parents[1] / "data" / "official_curriculum_seed_2026_2027.json"
REFERENCE_TOPICS = {"Как устроено общество", "Государство", "Культура. Искусство"}


def _social_studies_grade_nine():
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    curriculum = next(item for item in data["curricula"] if item["key"] == "SOCIAL_9_BASIC_2026_27")
    topics = {
        topic["title"]: (unit["title"], topic)
        for unit in curriculum["units"]
        for topic in unit["topics"]
    }
    return data, curriculum, topics


def _pilot_card(seed_topic, curriculum):
    source_key = curriculum["official_source"]
    exam_source_keys = sorted({
        link["source_key"]
        for link in seed_topic.get("exam_links", [])
        if link.get("source_key")
    })
    return {
        "subject": {"code": "SOCIAL_STUDIES"},
        "grade": 9,
        "level": "basic",
        "topic": {
            "title": seed_topic["title"],
            "default_lesson_blueprint": seed_topic["default_lesson_blueprint"],
            "reflection_patterns": seed_topic["reflection_patterns"],
            "assessment_skills": seed_topic["assessment_skills"],
            "difficulty_level": seed_topic["difficulty_level"],
            "abstraction_level": seed_topic["abstraction_level"],
        },
        "aliases": seed_topic["aliases"],
        "key_concepts": [{"term": item["term"]} for item in seed_topic["concepts"]],
        "skills": seed_topic["skills"],
        "interdisciplinary_links": seed_topic["interdisciplinary_links"],
        "exam_links": seed_topic["exam_links"],
        "learning_outcomes": [{"text": item["text"]} for item in seed_topic["outcomes"]],
        "typical_misconceptions": seed_topic["typical_misconceptions"],
        "common_examples": seed_topic["common_examples"],
        "counterexamples": seed_topic["counterexamples"],
        "essential_questions": seed_topic["essential_questions"],
        "source_references": [
            {"source_key": source_key, "source_role": "official_program"},
            *[
                {"source_key": exam_key, "source_role": "exam"}
                for exam_key in exam_source_keys
            ],
        ],
    }


def test_seed_has_three_reference_topic_cards_with_explicit_provenance():
    data, curriculum, topics = _social_studies_grade_nine()
    assert REFERENCE_TOPICS <= topics.keys()
    source = next(item for item in data["sources"] if item["key"] == curriculum["official_source"])
    assert source["status"] == "official"
    assert source["url"].startswith("https://edsoo.ru/")

    expected_hours = {"Как устроено общество": 2, "Государство": 2, "Культура. Искусство": 1}
    for title in REFERENCE_TOPICS:
        _, topic = topics[title]
        assert topic["hours"] == expected_hours[title]
        assert topic["suitable_activities"] == topic["default_lesson_blueprint"]["recommended_activities"]
        assert topic["verification_status"] == "pending_field_verification"
        assert topic["provenance"]["topic"]["origin"] == "official_direct"
        assert topic["provenance"]["learning_outcomes"]["origin"] == "generated_candidate"
        assert topic["provenance"]["learning_outcomes"]["status"] == "pending_field_verification"
        assert topic["provenance"]["content_summary"]["status"] == "pending_enrichment"
        assert topic["common_examples"] == []
        assert topic["counterexamples"] == []


def test_importer_marks_missing_and_generated_candidate_fields_conservatively():
    _, _, topics = _social_studies_grade_nine()
    topic = topics["Как устроено общество"][1]
    provenance = topic_card_provenance(topic, "SOCIAL_9_2026")

    assert provenance["learning_outcomes"]["origin"] == "generated_candidate"
    assert provenance["learning_outcomes"]["status"] == "pending_field_verification"
    assert provenance["content_summary"]["status"] == "pending_enrichment"
    assert provenance["common_examples"]["status"] == "pending_enrichment"
    assert provenance["topic"]["origin"] == "official_direct"


def test_importer_does_not_clear_existing_data_from_empty_seed_values():
    target = SimpleNamespace(common_examples=["existing reviewed example"], description="existing summary")

    set_if_available(target, "common_examples", [])
    set_if_available(target, "description", None)

    assert target.common_examples == ["existing reviewed example"]
    assert target.description == "existing summary"


def test_pilot_enrichment_uses_only_existing_seed_evidence_and_stays_pending_review():
    _, curriculum, topics = _social_studies_grade_nine()
    seed_topic = topics["Как устроено общество"][1]
    topic = SimpleNamespace(
        content_summary=None,
        common_examples=[],
        counterexamples=[],
        typical_misconceptions=seed_topic["typical_misconceptions"],
        essential_questions=seed_topic["essential_questions"],
        suitable_activities=[],
        default_lesson_blueprint=seed_topic["default_lesson_blueprint"],
        provenance=seed_topic["provenance"],
        derivation_status="pending_enrichment",
        verification_status="pending_field_verification",
    )
    card = _pilot_card(seed_topic, curriculum)

    patch = build_topic_card_enrichment(topic, card)

    assert len(patch["content_summary"].split(". ")) in range(3, 7)
    assert "общество" in patch["content_summary"]
    assert "взаимосвязанных элементов" in patch["content_summary"]
    assert len(patch["common_examples"]) == 3
    assert len(patch["counterexamples"]) == 2
    assert len(patch["typical_misconceptions"]) == 3
    assert len(patch["essential_questions"]) == 3
    assert len(patch["suitable_activities"]) == 4
    assert all({"activity", "purpose", "student_action"} <= row.keys() for row in patch["suitable_activities"])
    assert patch["provenance"]["content_summary"]["origin"] == "generated_candidate"
    assert patch["provenance"]["content_summary"]["status"] == "pending_review"
    assert patch["provenance"]["common_examples"]["origin"] == "methodical_mapping"
    assert patch["provenance"]["counterexamples"]["origin"] == "methodical_mapping"
    assert patch["provenance"]["typical_misconceptions"]["origin"] == "generated_candidate"
    assert patch["provenance"]["essential_questions"]["origin"] == "generated_candidate"
    assert patch["provenance"]["suitable_activities"]["origin"] == "methodical_mapping"
    assert patch["provenance"]["learning_outcomes"]["origin"] == "generated_candidate"
    assert patch["provenance"]["key_concepts"]["origin"] == "methodical_mapping"
    assert patch["provenance"]["exam_links"]["source_key"] == "FIPI_OGE_2027_PROJECTS"
    assert patch["provenance"]["source_references"]["origin"] == "official_direct"
    assert patch["provenance"]["default_lesson_blueprint"]["role"] == "system_fallback"
    assert patch["provenance"]["default_lesson_blueprint"]["specific_to_topic"] is False
    assert patch["provenance"]["reflection_patterns"]["role"] == "system_fallback"
    assert patch["provenance"]["reflection_patterns"]["specific_to_topic"] is False
    assert patch["derivation_status"] == "mixed_official_and_methodical"
    assert patch["verification_status"] == "pending_review"
    apply_topic_card_enrichment(topic, patch)
    assert build_topic_card_enrichment(topic, card) == {}


def test_pilot_enrichment_is_idempotent_and_does_not_overwrite_existing_fields():
    _, curriculum, topics = _social_studies_grade_nine()
    seed_topic = topics["Как устроено общество"][1]
    summary = "Reviewed local summary"
    topic = SimpleNamespace(
        content_summary=summary,
        common_examples=["reviewed"],
        counterexamples=["reviewed"],
        typical_misconceptions=["reviewed"],
        essential_questions=["reviewed"],
        suitable_activities=["existing_activity"],
        default_lesson_blueprint=seed_topic["default_lesson_blueprint"],
        provenance={
            key: {"origin": "methodical_mapping", "status": "reviewed"}
            for key in (
                "content_summary",
                "common_examples",
                "counterexamples",
                "typical_misconceptions",
                "essential_questions",
                "suitable_activities",
            )
        } | {
            "default_lesson_blueprint": {
                "origin": "methodical_mapping",
                "status": "pending_review",
                "role": "system_fallback",
                "specific_to_topic": False,
            },
            "reflection_patterns": {
                "origin": "methodical_mapping",
                "status": "pending_review",
                "role": "system_fallback",
                "specific_to_topic": False,
            },
        },
        derivation_status="mixed_official_and_methodical",
        verification_status="verified",
    )
    card = _pilot_card(seed_topic, curriculum)

    patch = build_topic_card_enrichment(topic, card)

    assert "content_summary" not in patch
    assert "common_examples" not in patch
    assert "counterexamples" not in patch
    assert "typical_misconceptions" not in patch
    assert "essential_questions" not in patch
    assert "suitable_activities" not in patch
    assert topic.content_summary == summary
    assert topic.suitable_activities == ["existing_activity"]
    assert topic.common_examples == ["reviewed"]
    assert topic.counterexamples == ["reviewed"]
    assert topic.typical_misconceptions == ["reviewed"]
    assert topic.essential_questions == ["reviewed"]
    assert topic.verification_status == "verified"


def test_pilot_enrichment_requires_linked_concepts_and_outcomes_for_summary():
    topic = SimpleNamespace(
        content_summary=None,
        suitable_activities=[],
        default_lesson_blueprint={},
        provenance={},
        derivation_status="pending_enrichment",
        verification_status="pending_verification",
    )

    patch = build_topic_card_enrichment(
        topic,
        {
            "subject": {"code": "SOCIAL_STUDIES"},
            "grade": 9,
            "level": "basic",
            "topic": {"title": "Как устроено общество"},
            "key_concepts": [],
            "learning_outcomes": [],
            "source_references": [],
        },
    )

    assert "content_summary" not in patch
    assert "suitable_activities" not in patch
    assert patch == {}


def test_pilot_enrichment_does_not_summarize_without_an_official_source_link():
    topic = SimpleNamespace(
        content_summary=None,
        suitable_activities=[],
        default_lesson_blueprint={},
        provenance={},
        derivation_status="pending_enrichment",
        verification_status="pending_verification",
    )
    card = {
        "subject": {"code": "SOCIAL_STUDIES"},
        "grade": 9,
        "level": "basic",
        "topic": {"title": "Как устроено общество"},
        "key_concepts": [{"term": "общество"}],
        "learning_outcomes": [{"text": "связанный результат"}],
        "source_references": [],
    }

    patch = build_topic_card_enrichment(topic, card)

    assert patch == {}


def test_pilot_enrichment_is_scoped_to_the_single_pilot_card():
    _, curriculum, topics = _social_studies_grade_nine()
    seed_topic = topics["Как устроено общество"][1]
    topic = SimpleNamespace(
        content_summary=None,
        common_examples=[],
        counterexamples=[],
        typical_misconceptions=[],
        essential_questions=[],
        suitable_activities=[],
        default_lesson_blueprint={},
        provenance={},
        derivation_status="pending_enrichment",
        verification_status="pending_verification",
    )
    card = _pilot_card(seed_topic, curriculum)
    card["grade"] = 10

    assert build_topic_card_enrichment(topic, card) == {}


def test_catalog_api_mapper_emits_topic_card_contract_and_source_reference():
    source_id = uuid4()
    topic_id = uuid4()
    source = SimpleNamespace(
        id=source_id,
        source_key="SOCIAL_9_2026",
        title="Федеральная рабочая программа. Обществознание. 9 класс",
        source_url=None,
        metadata_json={"official_url": "https://edsoo.ru/official.pdf"},
        verification_status=None,
        origin="official",
        status="official",
        author=None,
    )
    subject = SimpleNamespace(id=uuid4(), code="SOCIAL_STUDIES", name="Обществознание")
    grade = SimpleNamespace(grade=9)
    curriculum = SimpleNamespace(
        id=uuid4(), subject=subject, grade_level=grade, level="basic",
        title="Обществознание. 9 класс", version="2026-09/current-FRP",
        status="current", review_status="reviewed",
    )
    unit = SimpleNamespace(id=uuid4(), curriculum=curriculum, title="Человек и общество", order_index=1, recommended_hours=7)
    concept = SimpleNamespace(term="общество", id=uuid4(), definition_reference=None)
    outcome = SimpleNamespace(
        id=uuid4(), outcome_type="subject", outcome_subtype="conceptual",
        text="Тестовый outcome из seed", source_reference="https://edsoo.ru/official.pdf",
    )
    skill = SimpleNamespace(id=uuid4(), code="identify", name="Определять", category="cognitive")
    interdisciplinary = SimpleNamespace(
        related_subject="HISTORY", related_topic=None, link_type="historical_context",
        description="Связь с историческим контекстом", strength="useful",
    )
    exam = SimpleNamespace(
        exam="OGE_SOCIAL_STUDIES", exam_year=2027, exam_section=None,
        task_types=[], codifier_reference=None, importance="normal",
    )
    outcome_link = SimpleNamespace(outcome_id=outcome.id, priority=1)
    concept_link = SimpleNamespace(concept_id=concept.id, importance="required")
    skill_link = SimpleNamespace(skill_id=skill.id, priority=1)
    source_link = SimpleNamespace(
        source_id=source.id, source_role="official_program", section="Человек и общество",
        pages=None, priority=1,
    )
    topic = SimpleNamespace(
        id=topic_id, unit_id=unit.id,
        title="Как устроено общество", order_index=1, topic_type="new_content",
        recommended_hours=2, aliases=[],
        description=None, content_summary=None, suitable_activities=["case_analysis"],
        provenance={"topic": {"origin": "official_direct"}},
        derivation_status="mixed_official_and_methodical",
        verification_status="pending_field_verification",
        default_lesson_blueprint={}, typical_misconceptions=[], common_examples=[],
        counterexamples=[], essential_questions=[], reflection_patterns=[],
        assessment_skills=[], difficulty_level=None, abstraction_level=None,
        prerequisite_topic_ids=[], review_status="reviewed",
    )

    class Result:
        def __init__(self, index):
            self.index = index

        def scalar_one_or_none(self):
            return topic

        def one_or_none(self):
            return unit, curriculum, subject, grade

        def all(self):
            return {
                2: [(outcome_link, outcome)],
                3: [(concept_link, concept)],
                4: [(skill_link, skill)],
                5: [(source_link, source)],
            }.get(self.index, [])

        def scalars(self):
            values = {6: [interdisciplinary], 7: [exam]}.get(self.index, [])
            return SimpleNamespace(all=lambda: values)

    class Session:
        def __init__(self):
            self.statements = []

        async def execute(self, _statement):
            from sqlalchemy.dialects import postgresql

            _statement.compile(dialect=postgresql.dialect())
            index = len(self.statements)
            self.statements.append(_statement)
            return Result(index)

    session = Session()
    card = asyncio.run(CurriculumCatalogService().get_topic_card(session, topic_id))
    validated = TopicCardOut.model_validate(card)

    assert validated.subject["code"] == "SOCIAL_STUDIES"
    assert validated.grade == 9
    assert validated.level == "basic"
    assert validated.hours == 2
    assert validated.learning_outcomes[0]["text"] == "Тестовый outcome из seed"
    assert validated.key_concepts[0]["term"] == "общество"
    assert validated.skills[0]["code"] == "identify"
    assert validated.source_references[0]["url"] == "https://edsoo.ru/official.pdf"
    assert validated.interdisciplinary_links[0]["related_subject"] == "HISTORY"
    assert validated.exam_links[0]["exam"] == "OGE_SOCIAL_STUDIES"
    assert validated.verification_status == "pending_field_verification"
    assert len(session.statements) == 8


def test_topic_search_query_uses_explicit_join_left_sides():
    class Result:
        def all(self):
            return []

    class Session:
        async def execute(self, statement):
            from sqlalchemy.dialects import postgresql

            statement.compile(dialect=postgresql.dialect())
            return Result()

    rows = asyncio.run(CurriculumCatalogService().search_topics(
        Session(),
        q="Как устроено общество",
        subject_code="SOCIAL_STUDIES",
        grade=9,
        level="basic",
        limit=1,
    ))

    assert rows == []


def test_topic_card_sanitizer_removes_enrich_placeholders():
    from app.services.topic_card_enrichment import sanitize_topic_card_output

    raw = {
        "content_summary": "ENRICH",
        "common_examples": ["ENRICH", {"title": "Реальный пример"}],
        "topic": {
            "description": "ENRICH",
            "essential_questions": ["ENRICH"],
        },
    }

    cleaned = sanitize_topic_card_output(raw)

    assert cleaned["content_summary"] is None
    assert cleaned["common_examples"] == [{"title": "Реальный пример"}]
    assert cleaned["topic"]["description"] is None
    assert cleaned["topic"]["essential_questions"] == []

def test_enrichment_uses_official_url_when_source_key_is_null():
    from types import SimpleNamespace

    from app.services.topic_card_enrichment import build_topic_card_enrichment

    topic = SimpleNamespace(
        content_summary=None,
        common_examples=[],
        counterexamples=[],
        typical_misconceptions=[],
        essential_questions=[],
        suitable_activities=[],
        provenance={},
        derivation_status="pending_enrichment",
    )

    card = {
        "subject": {"code": "SOCIAL_STUDIES"},
        "grade": 9,
        "level": "basic",
        "topic": {
            "title": "Как устроено общество",
            "default_lesson_blueprint": {},
        },
        "source_references": [
            {
                "source_key": None,
                "url": "https://edsoo.ru/official-program.pdf",
                "source_role": "official_program",
            },
            {
                "source_key": None,
                "url": "https://fipi.ru/exam.pdf",
                "source_role": "exam",
            },
        ],
        "key_concepts": [{"term": "общество"}],
        "learning_outcomes": [{"text": "раскрывать смысл понятия «общество»"}],
        "skills": [],
        "interdisciplinary_links": [],
        "exam_links": [],
        "aliases": [],
    }

    patch = build_topic_card_enrichment(topic, card)

    assert "content_summary" in patch
    assert patch["content_summary"]
    assert (
        patch["provenance"]["content_summary"]["source_keys"]
        == ["https://edsoo.ru/official-program.pdf"]
    )
