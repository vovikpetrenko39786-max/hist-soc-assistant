"""Import the universal official curriculum seed for academic year 2026/2027.

The importer is deliberately idempotent by curriculum version/order indexes.
It imports GLOBAL curriculum data only; no teacher, class or student data.

Dataset v0.4 also imports Topic Card enrichment:
- normalized learning outcomes;
- concepts;
- skills;
- methodical blueprints;
- interdisciplinary links;
- broad exam links and FIPI source links.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.catalog import (
    Concept,
    Curriculum,
    CurriculumUnit,
    ExamLink,
    GradeLevel,
    InterdisciplinaryLink,
    LearningOutcome,
    Skill,
    Subject,
    Topic,
    TopicConcept,
    TopicOutcome,
    TopicSkill,
    TopicSource,
)
from app.models.entities import Source

DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "data" / "official_curriculum_seed_2026_2027.json"


def education_level(grade: int) -> str:
    if grade <= 4:
        return "primary_general"
    if grade <= 9:
        return "basic_general"
    return "secondary_general"


async def get_or_create_subject(session, code: str) -> Subject:
    subject = await session.scalar(select(Subject).where(Subject.code == code))
    if subject:
        return subject
    names = {
        "HISTORY": "История",
        "SOCIAL_STUDIES": "Обществознание",
        "INDIVIDUAL_PROJECT": "Индивидуальный проект",
    }
    subject = Subject(code=code, name=names.get(code, code))
    session.add(subject)
    await session.flush()
    return subject


async def get_or_create_grade(session, grade: int) -> GradeLevel:
    row = await session.scalar(select(GradeLevel).where(GradeLevel.grade == grade))
    if row:
        return row
    row = GradeLevel(grade=grade, education_level=education_level(grade), label=f"{grade} класс")
    session.add(row)
    await session.flush()
    return row


async def upsert_source(session, item: dict) -> Source:
    source = await session.scalar(
        select(Source).where(Source.title == item["title"], Source.source_type == item["source_type"])
    )
    meta = {"catalog_key": item["key"], "official_url": item["url"], "coverage": item.get("coverage")}
    if source is None:
        source = Source(
            title=item["title"],
            author=None,
            subject=item.get("subject"),
            grade=None,
            year=item.get("year"),
            source_type=item["source_type"],
            status=item["status"],
            origin=item.get("origin"),
            access_status=item.get("access_status"),
            is_current=True,
            metadata_json=meta,
        )
        session.add(source)
        await session.flush()
    else:
        source.year = item.get("year")
        source.status = item["status"]
        source.origin = item.get("origin")
        source.access_status = item.get("access_status")
        source.is_current = True
        source.metadata_json = {**(source.metadata_json or {}), **meta}
    return source


async def get_or_create_outcome(session, subject, grade, item: dict, source_url: str) -> LearningOutcome:
    source_reference = item.get("source_reference") or source_url
    row = await session.scalar(
        select(LearningOutcome).where(
            LearningOutcome.subject_id == subject.id,
            LearningOutcome.grade_level_id == grade.id,
            LearningOutcome.outcome_type == item["type"],
            LearningOutcome.outcome_subtype == item.get("subtype"),
            LearningOutcome.text == item["text"],
        )
    )
    if row is None:
        row = LearningOutcome(
            subject_id=subject.id,
            grade_level_id=grade.id,
            outcome_type=item["type"],
            outcome_subtype=item.get("subtype"),
            text=item["text"],
            source_reference=source_reference,
            review_status=item.get("review_status", "reviewed"),
        )
        session.add(row)
        await session.flush()
    return row


async def get_or_create_concept(session, subject, term: str, source_url: str) -> Concept:
    row = await session.scalar(
        select(Concept).where(Concept.subject_id == subject.id, Concept.term == term)
    )
    if row is None:
        row = Concept(subject_id=subject.id, term=term, definition_reference=source_url)
        session.add(row)
        await session.flush()
    return row


async def get_or_create_skill(session, code: str) -> Skill:
    row = await session.scalar(select(Skill).where(Skill.code == code))
    if row:
        return row
    labels = {
        "identify": ("Определять и распознавать", "cognitive"),
        "compare": ("Сравнивать", "cognitive"),
        "classify": ("Классифицировать", "cognitive"),
        "explain": ("Объяснять", "cognitive"),
        "give_example": ("Приводить конкретный пример", "subject"),
        "argue": ("Аргументировать позицию", "communicative"),
        "analyze_source": ("Анализировать источник", "subject"),
        "analyze_map": ("Анализировать карту", "subject"),
        "establish_causality": ("Устанавливать причинно-следственные связи", "cognitive"),
        "build_plan": ("Структурировать материал и составлять план", "regulatory"),
        "interpret_statistics": ("Интерпретировать статистические данные", "cognitive"),
        "apply_concept": ("Применять понятие к новой ситуации", "subject"),
    }
    name, category = labels.get(code, (code, "other"))
    row = Skill(code=code, name=name, category=category)
    session.add(row)
    await session.flush()
    return row


async def import_topic_card(
    session,
    *,
    topic: Topic,
    topic_item: dict,
    subject: Subject,
    grade: GradeLevel,
    official_source: Source,
    source_map: dict[str, Source],
    counts: dict,
) -> None:
    source_url = official_source.metadata_json.get("official_url")

    topic.description = topic_item.get("description")
    topic.default_lesson_blueprint = topic_item.get("default_lesson_blueprint", {})
    topic.typical_misconceptions = topic_item.get("typical_misconceptions", [])
    topic.common_examples = topic_item.get("common_examples", [])
    topic.counterexamples = topic_item.get("counterexamples", [])
    topic.essential_questions = topic_item.get("essential_questions", [])
    topic.reflection_patterns = topic_item.get("reflection_patterns", [])
    topic.assessment_skills = topic_item.get("assessment_skills", [])
    topic.difficulty_level = topic_item.get("difficulty_level")
    topic.abstraction_level = topic_item.get("abstraction_level")
    topic.prerequisite_topic_ids = topic_item.get("prerequisite_topic_ids", [])

    for priority, item in enumerate(topic_item.get("outcomes", []), start=1):
        outcome = await get_or_create_outcome(session, subject, grade, item, source_url)
        link = await session.scalar(
            select(TopicOutcome).where(
                TopicOutcome.topic_id == topic.id,
                TopicOutcome.outcome_id == outcome.id,
            )
        )
        if link is None:
            session.add(TopicOutcome(topic_id=topic.id, outcome_id=outcome.id, priority=priority))
            counts["topic_outcomes"] += 1
        else:
            link.priority = priority

    for item in topic_item.get("concepts", []):
        concept = await get_or_create_concept(session, subject, item["term"], source_url)
        link = await session.scalar(
            select(TopicConcept).where(
                TopicConcept.topic_id == topic.id,
                TopicConcept.concept_id == concept.id,
            )
        )
        if link is None:
            session.add(
                TopicConcept(
                    topic_id=topic.id,
                    concept_id=concept.id,
                    importance=item.get("importance", "required"),
                )
            )
            counts["topic_concepts"] += 1
        else:
            link.importance = item.get("importance", "required")

    for priority, code in enumerate(topic_item.get("skills", []), start=1):
        skill = await get_or_create_skill(session, code)
        link = await session.scalar(
            select(TopicSkill).where(TopicSkill.topic_id == topic.id, TopicSkill.skill_id == skill.id)
        )
        if link is None:
            session.add(TopicSkill(topic_id=topic.id, skill_id=skill.id, priority=priority))
            counts["topic_skills"] += 1
        else:
            link.priority = priority

    # These two lists are replaced on every import so the dataset remains authoritative.
    await session.execute(delete(InterdisciplinaryLink).where(InterdisciplinaryLink.topic_id == topic.id))
    for item in topic_item.get("interdisciplinary_links", []):
        session.add(
            InterdisciplinaryLink(
                topic_id=topic.id,
                related_subject=item["related_subject"],
                related_topic=item.get("related_topic"),
                link_type=item.get("link_type"),
                description=item["description"],
                strength=item.get("strength", "optional"),
            )
        )
        counts["interdisciplinary_links"] += 1

    await session.execute(delete(ExamLink).where(ExamLink.topic_id == topic.id))
    for item in topic_item.get("exam_links", []):
        source_key = item.get("source_key")
        exam_source = source_map.get(source_key) if source_key else None
        exam_meta = {
            "mapping_level": item.get("mapping_level", "general_topic"),
            "source_key": source_key,
            "source_url": exam_source.metadata_json.get("official_url") if exam_source else None,
            "status": "project" if item.get("exam_year") == 2027 else None,
        }
        session.add(
            ExamLink(
                topic_id=topic.id,
                exam=item["exam"],
                exam_year=item.get("exam_year"),
                exam_section=item.get("exam_section"),
                task_types=item.get("task_types", []),
                codifier_reference=item.get("codifier_reference"),
                importance=item.get("importance", "normal"),
            )
        )
        counts["exam_links"] += 1
        if exam_source is not None:
            source_link = await session.scalar(
                select(TopicSource).where(
                    TopicSource.topic_id == topic.id,
                    TopicSource.source_id == exam_source.id,
                    TopicSource.source_role == "exam",
                )
            )
            if source_link is None:
                session.add(
                    TopicSource(
                        topic_id=topic.id,
                        source_id=exam_source.id,
                        source_role="exam",
                        priority=20,
                        notes="Общая связь темы с проектами документов ФИПИ 2027; точный кодификаторный маппинг выполняется отдельно",
                    )
                )
                counts["exam_source_links"] += 1


async def import_dataset(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    counts = {
        "sources": 0,
        "curricula": 0,
        "units": 0,
        "topics": 0,
        "topic_outcomes": 0,
        "topic_concepts": 0,
        "topic_skills": 0,
        "interdisciplinary_links": 0,
        "exam_links": 0,
        "exam_source_links": 0,
    }
    async with SessionLocal() as session:
        source_map: dict[str, Source] = {}
        for item in payload["sources"]:
            source_map[item["key"]] = await upsert_source(session, item)
            counts["sources"] += 1

        for item in payload["curricula"]:
            subject = await get_or_create_subject(session, item["subject"])
            grade = await get_or_create_grade(session, item["grade"])
            official_source = source_map[item["official_source"]]

            curriculum = await session.scalar(
                select(Curriculum).where(
                    Curriculum.subject_id == subject.id,
                    Curriculum.grade_level_id == grade.id,
                    Curriculum.level == item["level"],
                    Curriculum.version == item["version"],
                )
            )
            metadata = {
                "catalog_key": item["key"],
                "dataset": payload["dataset"],
                "dataset_version": payload["dataset_version"],
                "academic_year": payload["academic_year"],
                "coverage": item.get("coverage"),
                "structure_method": item.get("structure_method"),
                "content_provenance": item.get("content_provenance"),
                "total_hours": item.get("total_hours"),
                "official_url": official_source.metadata_json.get("official_url"),
            }
            if curriculum is None:
                curriculum = Curriculum(
                    subject_id=subject.id,
                    grade_level_id=grade.id,
                    level=item["level"],
                    title=item["title"],
                    version=item["version"],
                    status=item.get("status", "current"),
                    official_source_id=official_source.id,
                    review_status=item.get("review_status", "draft"),
                    metadata_json=metadata,
                )
                session.add(curriculum)
                await session.flush()
            else:
                curriculum.title = item["title"]
                curriculum.status = item.get("status", "current")
                curriculum.official_source_id = official_source.id
                curriculum.review_status = item.get("review_status", "draft")
                curriculum.metadata_json = {**(curriculum.metadata_json or {}), **metadata}
            counts["curricula"] += 1

            for unit_index, unit_item in enumerate(item.get("units", []), start=1):
                unit = await session.scalar(
                    select(CurriculumUnit).where(
                        CurriculumUnit.curriculum_id == curriculum.id,
                        CurriculumUnit.order_index == unit_index,
                    )
                )
                if unit is None:
                    unit = CurriculumUnit(curriculum_id=curriculum.id, title=unit_item["title"], order_index=unit_index)
                    session.add(unit)
                    await session.flush()
                unit.title = unit_item["title"]
                unit.recommended_hours = unit_item.get("hours")
                unit.description = unit_item.get("description")
                unit.source_reference = official_source.metadata_json.get("official_url")
                unit.review_status = item.get("review_status", "draft")
                counts["units"] += 1

                for topic_index, topic_item in enumerate(unit_item.get("topics", []), start=1):
                    topic = await session.scalar(
                        select(Topic).where(Topic.unit_id == unit.id, Topic.order_index == topic_index)
                    )
                    if topic is None:
                        topic = Topic(unit_id=unit.id, title=topic_item["title"], order_index=topic_index)
                        session.add(topic)
                    topic.title = topic_item["title"]
                    topic.aliases = topic_item.get("aliases", [])
                    topic.recommended_hours = topic_item.get("hours")
                    topic.topic_type = topic_item.get("topic_type", "new_content")
                    topic.review_status = item.get("review_status", "draft")
                    topic.metadata_json = {
                        **(topic.metadata_json or {}),
                        "dataset": payload["dataset"],
                        "dataset_version": payload["dataset_version"],
                        "curriculum_key": item["key"],
                        "coverage": item.get("coverage"),
                        "structure_method": item.get("structure_method"),
                        "official_url": official_source.metadata_json.get("official_url"),
                    }
                    await session.flush()

                    source_link = await session.scalar(
                        select(TopicSource).where(
                            TopicSource.topic_id == topic.id,
                            TopicSource.source_id == official_source.id,
                            TopicSource.source_role == "official_program",
                        )
                    )
                    if source_link is None:
                        source_link = TopicSource(
                            topic_id=topic.id,
                            source_id=official_source.id,
                            source_role="official_program",
                            priority=1,
                        )
                        session.add(source_link)
                    source_link.section = unit_item["title"]
                    source_link.notes = "Связь с действующей федеральной рабочей программой"

                    await import_topic_card(
                        session,
                        topic=topic,
                        topic_item=topic_item,
                        subject=subject,
                        grade=grade,
                        official_source=official_source,
                        source_map=source_map,
                        counts=counts,
                    )
                    counts["topics"] += 1

        await session.commit()
    return counts


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args()
    counts = await import_dataset(args.dataset)
    print(json.dumps(counts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
