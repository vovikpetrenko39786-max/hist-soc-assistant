"""Exercise the protected export path against the disposable CI database.

This is deliberately isolated from Railway, Telegram, production credentials,
and real student data. It fails closed unless the dedicated CI database and
test environment are selected.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import secrets
import tempfile
import uuid
import zipfile
from pathlib import Path

import httpx

from ci_db_schema_smoke import validated_ci_database_url


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def configure_isolated_environment(
    output_dir: str,
    class_course_id: uuid.UUID,
) -> tuple[str, str]:
    if os.getenv("APP_ENV") != "test":
        raise RuntimeError("Refusing release smoke outside APP_ENV=test")
    if os.getenv("RAILWAY_SERVICE_ID") or os.getenv("RAILWAY_ENVIRONMENT_ID"):
        raise RuntimeError("Refusing release smoke inside a Railway environment")
    validated_ci_database_url(os.getenv("DATABASE_URL"))

    admin_key = secrets.token_urlsafe(48)
    pilot_key = secrets.token_urlsafe(48)
    os.environ["ADMIN_API_KEY"] = admin_key
    os.environ["PILOT_API_KEY"] = pilot_key
    os.environ["TELEGRAM_ALLOWED_USER_IDS"] = "10001,10002"
    os.environ["TELEGRAM_COURSE_BINDINGS_JSON"] = json.dumps(
        {
            "10001": {
                "social_studies": {"class_course_id": str(class_course_id)},
            }
        }
    )
    os.environ["OUTPUT_STORAGE_DIR"] = output_dir
    return admin_key, pilot_key


def assessment_artifact() -> dict:
    return {
        "artifact_type": "assessment",
        "title": "CI: проверочная работа",
        "grade": 10,
        "subject": "SOCIAL_STUDIES",
        "assessment_type": "check",
        "time_minutes": 15,
        "instructions": "Выполните задания самостоятельно.",
        "tasks": [
            {
                "number": 1,
                "instruction": "Дайте определение понятия «социальный институт».",
                "skill": "Определение",
                "difficulty": "basic",
                "points": 2,
                "student_data": None,
                "answer": "Устойчивая форма организации совместной деятельности людей.",
                "criteria": "2 балла: раскрыт смысл и указан общественный характер.",
            }
        ],
        "max_points": 2,
        "grading_scale": {"5": "85-100%"},
        "common_errors_to_watch": ["Не путать институт и организацию."],
        "source_references": [],
    }


def course_fixture_ids() -> dict[str, uuid.UUID | str]:
    suffix = uuid.uuid4().hex[:12]
    return {
        "subject": uuid.uuid4(),
        "grade": uuid.uuid4(),
        "curriculum": uuid.uuid4(),
        "unit": uuid.uuid4(),
        "topic": uuid.uuid4(),
        "source": uuid.uuid4(),
        "topic_source": uuid.uuid4(),
        "chunk": uuid.uuid4(),
        "teacher": uuid.uuid4(),
        "class_group": uuid.uuid4(),
        "course": uuid.uuid4(),
        "class_course": uuid.uuid4(),
        "source_key": f"CI-SOC-10-{suffix}",
        "course_code": f"CI-SOCIAL-10-{suffix}",
        "curriculum_version": f"ci-{suffix}",
    }


async def seed_course_fixture(session_factory, fixture: dict[str, uuid.UUID | str]) -> None:
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
        Source,
        SourceChunk,
        Teacher,
    )

    async with session_factory() as session:
        session.add_all(
            [
                Subject(
                    id=fixture["subject"],
                    code="SOCIAL_STUDIES",
                    name="Обществознание (CI)",
                ),
                GradeLevel(
                    id=fixture["grade"],
                    grade=10,
                    education_level="secondary_general",
                    label="10 класс",
                ),
                Source(
                    id=fixture["source"],
                    source_key=fixture["source_key"],
                    title="Синтетический учебник CI",
                    subject="SOCIAL_STUDIES",
                    grade=10,
                    level="basic",
                    source_type="textbook",
                    status="official",
                    origin="ci_synthetic",
                    access_status="test_only",
                    page_count=1,
                    has_text_layer=True,
                    is_current=True,
                    authority_rank=100,
                    verification_status="verified",
                    ingestion_status="ready",
                    metadata_json={"synthetic": True},
                ),
                Curriculum(
                    id=fixture["curriculum"],
                    subject_id=fixture["subject"],
                    grade_level_id=fixture["grade"],
                    level="basic",
                    title="Синтетическая программа CI",
                    version=fixture["curriculum_version"],
                    status="current",
                    review_status="verified",
                ),
                CurriculumUnit(
                    id=fixture["unit"],
                    curriculum_id=fixture["curriculum"],
                    title="Человек и общество",
                    order_index=1,
                    recommended_hours=4,
                    review_status="verified",
                ),
                Topic(
                    id=fixture["topic"],
                    unit_id=fixture["unit"],
                    title="Социальные институты",
                    aliases=["социальный институт"],
                    order_index=1,
                    recommended_hours=1,
                    content_summary=(
                        "Социальные институты организуют устойчивые формы "
                        "совместной деятельности людей."
                    ),
                    essential_questions=[
                        "Как социальные институты упорядочивают общественную жизнь?"
                    ],
                    derivation_status="verified",
                    verification_status="verified",
                    review_status="verified",
                ),
                TopicSource(
                    id=fixture["topic_source"],
                    topic_id=fixture["topic"],
                    source_id=fixture["source"],
                    source_role="primary_textbook",
                    section="Социальные институты",
                    pages="42",
                    priority=1,
                ),
                SourceChunk(
                    id=fixture["chunk"],
                    source_id=fixture["source"],
                    chunk_index=0,
                    chapter="Человек и общество",
                    section="Социальные институты",
                    topic="Социальные институты",
                    page_pdf=47,
                    page_pdf_end=47,
                    page_print=42,
                    page_print_end=42,
                    content_type="main_text",
                    text=(
                        "Социальные институты — это устойчивые формы организации "
                        "совместной деятельности людей. К ним относятся семья, "
                        "образование, государство и религия. Они закрепляют нормы, "
                        "роли и ожидаемые способы поведения."
                    ),
                    char_count=215,
                    embedding_status="pending",
                    metadata_json={"synthetic": True},
                ),
                Teacher(
                    id=fixture["teacher"],
                    display_name="CI Teacher",
                    school_name="Synthetic CI School",
                ),
                ClassGroup(
                    id=fixture["class_group"],
                    teacher_id=fixture["teacher"],
                    name="10-А",
                    grade=10,
                    academic_year="2026/2027",
                    students_count=0,
                    general_level="basic",
                    notes="Synthetic CI fixture",
                ),
                Course(
                    id=fixture["course"],
                    code=fixture["course_code"],
                    name="Обществознание 10 класс (CI)",
                    subject="SOCIAL_STUDIES",
                    level="basic",
                    description="Synthetic CI fixture",
                ),
                ClassCourse(
                    id=fixture["class_course"],
                    class_id=fixture["class_group"],
                    course_id=fixture["course"],
                    teacher_id=fixture["teacher"],
                    hours_per_week=2,
                    group_name="10-А",
                    primary_source_id=fixture["source"],
                    notes="Synthetic CI fixture",
                ),
            ]
        )
        await session.commit()


async def cleanup_course_fixture(
    session_factory,
    fixture: dict[str, uuid.UUID | str],
) -> None:
    from sqlalchemy import delete

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
        ExportedFile,
        GenerationRun,
        Source,
        SourceChunk,
        Teacher,
    )

    async with session_factory() as session:
        run_ids = [
            row[0]
            for row in (
                await session.execute(
                    GenerationRun.__table__.select()
                    .with_only_columns(GenerationRun.id)
                    .where(GenerationRun.class_course_id == fixture["class_course"])
                )
            ).all()
        ]
        if run_ids:
            await session.execute(
                delete(ExportedFile).where(ExportedFile.generation_run_id.in_(run_ids))
            )
            await session.execute(delete(GenerationRun).where(GenerationRun.id.in_(run_ids)))
        await session.execute(
            delete(ClassCourse).where(ClassCourse.id == fixture["class_course"])
        )
        await session.execute(delete(ClassGroup).where(ClassGroup.id == fixture["class_group"]))
        await session.execute(delete(Course).where(Course.id == fixture["course"]))
        await session.execute(delete(Teacher).where(Teacher.id == fixture["teacher"]))
        await session.execute(delete(SourceChunk).where(SourceChunk.id == fixture["chunk"]))
        await session.execute(delete(TopicSource).where(TopicSource.id == fixture["topic_source"]))
        await session.execute(delete(Topic).where(Topic.id == fixture["topic"]))
        await session.execute(
            delete(CurriculumUnit).where(CurriculumUnit.id == fixture["unit"])
        )
        await session.execute(
            delete(Curriculum).where(Curriculum.id == fixture["curriculum"])
        )
        await session.execute(delete(Source).where(Source.id == fixture["source"]))
        await session.execute(delete(GradeLevel).where(GradeLevel.id == fixture["grade"]))
        await session.execute(delete(Subject).where(Subject.id == fixture["subject"]))
        await session.commit()


async def run_smoke(output_dir: Path) -> None:
    fixture = course_fixture_ids()
    admin_key, pilot_key = configure_isolated_environment(
        str(output_dir),
        fixture["class_course"],
    )

    # Import only after the isolated environment has been validated and set.
    from app.db.session import SessionLocal, engine
    from app.main import app
    from app.models.entities import ExportedFile

    export_id: uuid.UUID | None = None
    transport = httpx.ASGITransport(app=app)
    try:
        await seed_course_fixture(SessionLocal, fixture)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://ci.local",
        ) as client:
            health = await client.get("/health")
            require(health.status_code == 200, "Public health endpoint failed")

            readiness = await client.get("/ready")
            require(
                readiness.status_code == 200,
                f"Readiness endpoint failed: {readiness.text}",
            )
            require(readiness.json().get("ready") is True, "Readiness endpoint is not ready")

            unauthenticated = await client.get("/api/v1/outputs/templates")
            require(
                unauthenticated.status_code == 401,
                "Protected API accepted an unauthenticated request",
            )

            payload = {
                "artifact": assessment_artifact(),
                "artifact_type": "assessment",
                "audience": "teacher",
                "formats": ["docx"],
                "template_name": "school_clean",
                "filename_base": "ci_release_smoke",
            }
            pilot_attempt = await client.post(
                "/api/v1/outputs/render",
                json=payload,
                headers={
                    "X-Pilot-Key": pilot_key,
                    "X-Pilot-User-ID": "10001",
                },
            )
            require(
                pilot_attempt.status_code == 403,
                "Pilot user was allowed to call the admin-only render endpoint",
            )

            rendered = await client.post(
                "/api/v1/outputs/render",
                json=payload,
                headers={"X-Admin-Key": admin_key},
            )
            require(rendered.status_code == 200, f"DOCX render failed: {rendered.text}")
            body = rendered.json()
            require(body.get("artifact_type") == "assessment", "Unexpected artifact type")
            require(len(body.get("files", [])) == 1, "Expected exactly one rendered file")

            file_info = body["files"][0]
            export_id = uuid.UUID(file_info["export_id"])
            rendered_path = Path(file_info["file_path"]).resolve()
            require(
                rendered_path.is_relative_to(output_dir.resolve()),
                "Rendered file escaped the isolated output directory",
            )
            require(rendered_path.is_file(), "Rendered DOCX is missing")

            downloaded = await client.get(
                file_info["download_path"],
                headers={"X-Admin-Key": admin_key},
            )
            require(downloaded.status_code == 200, "Rendered DOCX download failed")
            require(
                downloaded.headers.get("content-type", "").startswith(
                    "application/vnd.openxmlformats-officedocument"
                ),
                "Rendered file has an unexpected content type",
            )
            require(len(downloaded.content) == file_info["size_bytes"], "DOCX size mismatch")
            require(
                hashlib.sha256(downloaded.content).hexdigest() == file_info["sha256"],
                "DOCX checksum mismatch",
            )
            with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
                document_xml = archive.read("word/document.xml").decode("utf-8")
            require("CI: проверочная работа" in document_xml, "DOCX content is incomplete")

        async with SessionLocal() as session:
            row = await session.get(ExportedFile, export_id)
            require(row is not None, "Export metadata was not persisted")
            require(row.status == "ready", "Export metadata has an unexpected status")
            require(row.sha256 == file_info["sha256"], "Persisted checksum mismatch")
            await session.delete(row)
            await session.commit()

        workflow_payload = {
            "message": (
                "10-А класс, обществознание. Сделай урок: Социальные институты. "
                "Word. Только по учебнику. Без интернета."
            ),
            "auto_render": True,
            "allow_web_fallback": False,
            "source_key": fixture["source_key"],
            "class_course_id": str(fixture["class_course"]),
        }
        pilot_headers = {
            "X-Pilot-Key": pilot_key,
            "X-Pilot-User-ID": "10001",
        }
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://ci.local",
        ) as client:
            wrong_course_owner = await client.post(
                "/api/v1/assistant",
                json=workflow_payload,
                headers={
                    "X-Pilot-Key": pilot_key,
                    "X-Pilot-User-ID": "10002",
                },
            )
            require(
                wrong_course_owner.status_code == 403,
                "A pilot user was allowed to use another user's course",
            )

            workflow = await client.post(
                "/api/v1/assistant",
                json=workflow_payload,
                headers=pilot_headers,
            )
            require(workflow.status_code == 200, f"Lesson workflow failed: {workflow.text}")
            workflow_body = workflow.json()
            require(workflow_body.get("status") == "completed", "Lesson workflow did not complete")
            results = workflow_body.get("results", [])
            require(len(results) == 1, "Expected one lesson workflow result")
            lesson = results[0]
            require(lesson.get("artifact_type") == "lesson", "Unexpected workflow artifact")
            require(lesson.get("status") == "generated", "Lesson failed quality checks")
            require(not lesson.get("web_used"), "Offline lesson workflow used the web")
            require(int(lesson.get("quality_score") or 0) >= 80, "Lesson quality score is too low")
            require(len(lesson.get("files", [])) == 1, "Lesson DOCX was not rendered")

            run_id = uuid.UUID(lesson["run_id"])
            workflow_file = lesson["files"][0]
            workflow_export_id = uuid.UUID(workflow_file["export_id"])
            lesson_download = await client.get(
                workflow_file["download_path"],
                headers=pilot_headers,
            )
            require(lesson_download.status_code == 200, "Pilot lesson download failed")
            with zipfile.ZipFile(io.BytesIO(lesson_download.content)) as archive:
                lesson_xml = archive.read("word/document.xml").decode("utf-8")
            require("Социальные институты" in lesson_xml, "Lesson DOCX has the wrong topic")

        from app.models.entities import GenerationRun

        async with SessionLocal() as session:
            run = await session.get(GenerationRun, run_id)
            require(run is not None, "Lesson generation run was not persisted")
            require(run.status == "generated", "Persisted lesson run is not generated")
            require(run.class_course_id == fixture["class_course"], "Lesson lost course scope")
            require(run.teacher_id == fixture["teacher"], "Lesson lost teacher scope")
            require(
                (run.request_json or {}).get("_owner_principal") == "telegram:10001",
                "Lesson export owner was not persisted",
            )
            require(bool((run.quality_report or {}).get("passed")), "Persisted quality gate failed")
            manifest = run.source_manifest or []
            require(bool(manifest), "Lesson has no textbook source manifest")
            require(
                all(item.get("source_key") == fixture["source_key"] for item in manifest),
                "Lesson used a source outside the selected textbook",
            )
            workflow_export = await session.get(ExportedFile, workflow_export_id)
            require(workflow_export is not None, "Lesson export metadata is missing")
            require(
                workflow_export.generation_run_id == run_id,
                "Lesson export is not linked to its generation run",
            )
            require(
                workflow_export.sha256 == hashlib.sha256(lesson_download.content).hexdigest(),
                "Lesson download checksum does not match persisted metadata",
            )

        await cleanup_course_fixture(SessionLocal, fixture)
    finally:
        await engine.dispose()


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="hist-soc-ci-release-smoke-") as directory:
        await run_smoke(Path(directory))
    print(
        "PASS: isolated pilot course -> textbook retrieval -> lesson -> "
        "PostgreSQL -> DOCX -> download smoke test"
    )


if __name__ == "__main__":
    asyncio.run(main())
