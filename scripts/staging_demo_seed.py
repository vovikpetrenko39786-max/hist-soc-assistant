"""Create the deterministic, synthetic dataset used by presentation staging.

The script refuses production and ordinary development environments. It is
idempotent and never reads or copies production data.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date
from typing import Mapping

from sqlalchemy import text


DEMO_DATASET_ID = "hist-soc-presentation-v1"
DEMO_USER_ID = 10001
DEMO_SOURCE_KEY = "DEMO-SOCIAL-10-2026"

SUBJECT_ID = uuid.UUID("0d32fb1e-69ea-4c8b-b9d8-e894a265b378")
GRADE_ID = uuid.UUID("e6b0c580-e44c-4a36-a4f6-389c04dc87f1")
CURRICULUM_ID = uuid.UUID("d7656931-393d-432c-949a-06639f5ee93f")
UNIT_ID = uuid.UUID("f6794183-63ac-45cd-920a-784a523491de")
TOPIC_ID = uuid.UUID("6e5d6fd4-8541-440e-883b-947589978b0d")
SOURCE_ID = uuid.UUID("5ae99b34-4097-4767-88f5-e3b317a12962")
TOPIC_SOURCE_ID = uuid.UUID("31bdbb46-d74d-474d-8e2f-dbec5d922c29")
CHUNK_ID = uuid.UUID("2451c69b-f141-45f6-a4d8-903db67b2f0e")
TEACHER_ID = uuid.UUID("a9550623-c924-46b9-be21-89f446580bc2")
CLASS_GROUP_ID = uuid.UUID("e04737b3-abac-473b-9f25-3e264e4614e4")
COURSE_ID = uuid.UUID("fe1f80bb-b033-4792-b8ba-824ab1c24874")
CLASS_COURSE_ID = uuid.UUID("a16f9b56-15e6-45e2-8834-80c6bd177af8")
LESSON_ID = uuid.UUID("f97ec6f6-1355-4f10-a1c7-da450e14b015")


def validate_staging_environment(env: Mapping[str, str]) -> None:
    if env.get("APP_ENV", "").strip().casefold() != "staging":
        raise RuntimeError("Demo seed requires APP_ENV=staging")
    if env.get("DEMO_SEED_ENABLED", "").strip().casefold() != "true":
        raise RuntimeError("Demo seed requires DEMO_SEED_ENABLED=true")
    if env.get("DEMO_DATASET_ID", "").strip() != DEMO_DATASET_ID:
        raise RuntimeError("Unexpected demo dataset identifier")
    environment_name = env.get("RAILWAY_ENVIRONMENT_NAME", "").strip().casefold()
    if environment_name != "staging":
        raise RuntimeError("Demo seed requires a staging-named environment")


async def add_if_missing(session, model, identifier: uuid.UUID, **values) -> bool:
    if await session.get(model, identifier) is not None:
        return False
    session.add(model(id=identifier, **values))
    await session.flush()
    return True


async def seed() -> int:
    validate_staging_environment(os.environ)

    import app.models  # noqa: F401
    from app.db.base import Base
    from app.db.session import SessionLocal, engine
    from app.models.catalog import (
        Curriculum,
        CurriculumUnit,
        GradeLevel,
        Subject,
        Topic,
        TopicSource,
    )
    from app.models.entities import (
        ClassCourse,
        ClassGroup,
        Course,
        Lesson,
        LessonStatus,
        Source,
        SourceChunk,
        Teacher,
    )

    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.create_all)

    created = 0
    async with SessionLocal() as session:
        created += await add_if_missing(
            session,
            Subject,
            SUBJECT_ID,
            code="SOCIAL_STUDIES",
            name="Обществознание — демонстрационный курс",
        )
        created += await add_if_missing(
            session,
            GradeLevel,
            GRADE_ID,
            grade=10,
            education_level="secondary_general",
            label="10 класс",
        )
        created += await add_if_missing(
            session,
            Source,
            SOURCE_ID,
            source_key=DEMO_SOURCE_KEY,
            title="Демонстрационный учебник по обществознанию",
            subject="SOCIAL_STUDIES",
            grade=10,
            level="basic",
            source_type="textbook",
            status="official",
            origin="staging_synthetic",
            access_status="demo_only",
            page_count=120,
            has_text_layer=True,
            is_current=True,
            authority_rank=100,
            verification_status="verified",
            ingestion_status="ready",
            metadata_json={"synthetic": True, "dataset": DEMO_DATASET_ID},
        )
        created += await add_if_missing(
            session,
            Curriculum,
            CURRICULUM_ID,
            subject_id=SUBJECT_ID,
            grade_level_id=GRADE_ID,
            level="basic",
            title="Демонстрационная программа: обществознание, 10 класс",
            version="demo-2026",
            status="current",
            review_status="verified",
            metadata_json={"synthetic": True},
        )
        created += await add_if_missing(
            session,
            CurriculumUnit,
            UNIT_ID,
            curriculum_id=CURRICULUM_ID,
            title="Человек и общество",
            order_index=1,
            recommended_hours=4,
            review_status="verified",
        )
        created += await add_if_missing(
            session,
            Topic,
            TOPIC_ID,
            unit_id=UNIT_ID,
            title="Социальные институты",
            aliases=["социальный институт", "институты общества"],
            order_index=1,
            recommended_hours=1,
            content_summary=(
                "Социальные институты организуют устойчивые формы "
                "совместной деятельности людей."
            ),
            essential_questions=[
                "Как социальные институты упорядочивают общественную жизнь?"
            ],
            common_examples=["семья", "образование", "государство", "религия"],
            derivation_status="verified",
            verification_status="verified",
            review_status="verified",
            metadata_json={"synthetic": True},
        )
        created += await add_if_missing(
            session,
            TopicSource,
            TOPIC_SOURCE_ID,
            topic_id=TOPIC_ID,
            source_id=SOURCE_ID,
            source_role="primary_textbook",
            section="Социальные институты",
            pages="42–43",
            priority=1,
        )
        created += await add_if_missing(
            session,
            SourceChunk,
            CHUNK_ID,
            source_id=SOURCE_ID,
            chunk_index=0,
            chapter="Человек и общество",
            section="Социальные институты",
            topic="Социальные институты",
            page_pdf=47,
            page_pdf_end=48,
            page_print=42,
            page_print_end=43,
            content_type="main_text",
            text=(
                "Социальные институты — это устойчивые формы организации "
                "совместной деятельности людей. Семья обеспечивает первичную "
                "социализацию, образование передаёт знания и культурный опыт, "
                "государство поддерживает общественный порядок. Институты "
                "закрепляют нормы, социальные роли и ожидаемые способы поведения."
            ),
            char_count=322,
            embedding_status="pending",
            metadata_json={"synthetic": True, "dataset": DEMO_DATASET_ID},
        )
        created += await add_if_missing(
            session,
            Teacher,
            TEACHER_ID,
            display_name="Демонстрационный учитель",
            school_name="Синтетическая школа",
            default_lesson_duration=45,
            timezone="Asia/Vladivostok",
            preferences={"synthetic": True},
        )
        created += await add_if_missing(
            session,
            ClassGroup,
            CLASS_GROUP_ID,
            teacher_id=TEACHER_ID,
            name="10-А",
            grade=10,
            academic_year="2026/2027",
            students_count=0,
            general_level="basic",
            notes="Только синтетические данные для презентации",
            is_active=True,
        )
        created += await add_if_missing(
            session,
            Course,
            COURSE_ID,
            code="DEMO-SOCIAL-10-2026",
            name="Обществознание, 10 класс — демонстрация",
            subject="SOCIAL_STUDIES",
            level="basic",
            description="Синтетический staging-курс",
        )
        created += await add_if_missing(
            session,
            ClassCourse,
            CLASS_COURSE_ID,
            class_id=CLASS_GROUP_ID,
            course_id=COURSE_ID,
            teacher_id=TEACHER_ID,
            hours_per_week=2,
            group_name="10-А",
            primary_source_id=SOURCE_ID,
            notes="Только синтетические данные для презентации",
            is_active=True,
        )
        created += await add_if_missing(
            session,
            Lesson,
            LESSON_ID,
            class_course_id=CLASS_COURSE_ID,
            date=date(2026, 11, 14),
            lesson_number=1,
            topic="Общество как система",
            lesson_type="combined",
            status=LessonStatus.completed,
            duration_minutes=45,
            completed_content="Понятие общества и основные сферы общественной жизни.",
            next_step="Социальные институты",
        )
        await session.commit()

    await engine.dispose()
    return created


async def main() -> None:
    created = await seed()
    print(
        "PASS: synthetic presentation dataset ready; "
        f"created={created}; class_course_id={CLASS_COURSE_ID}; source_key={DEMO_SOURCE_KEY}"
    )


if __name__ == "__main__":
    asyncio.run(main())
