import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.schemas.catalog import TopicCardOut
from app.services.catalog import CurriculumCatalogService
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
