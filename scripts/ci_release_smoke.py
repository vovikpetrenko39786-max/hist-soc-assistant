"""Exercise the protected export path against the disposable CI database.

This is deliberately isolated from Railway, Telegram, production credentials,
and real student data. It fails closed unless the dedicated CI database and
test environment are selected.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
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


def configure_isolated_environment(output_dir: str) -> tuple[str, str]:
    if os.getenv("APP_ENV") != "test":
        raise RuntimeError("Refusing release smoke outside APP_ENV=test")
    if os.getenv("RAILWAY_SERVICE_ID") or os.getenv("RAILWAY_ENVIRONMENT_ID"):
        raise RuntimeError("Refusing release smoke inside a Railway environment")
    validated_ci_database_url(os.getenv("DATABASE_URL"))

    admin_key = secrets.token_urlsafe(48)
    pilot_key = secrets.token_urlsafe(48)
    os.environ["ADMIN_API_KEY"] = admin_key
    os.environ["PILOT_API_KEY"] = pilot_key
    os.environ["TELEGRAM_ALLOWED_USER_IDS"] = "10001"
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


async def run_smoke(output_dir: Path) -> None:
    admin_key, pilot_key = configure_isolated_environment(str(output_dir))

    # Import only after the isolated environment has been validated and set.
    from app.db.session import SessionLocal, engine
    from app.main import app
    from app.models.entities import ExportedFile

    export_id: uuid.UUID | None = None
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://ci.local",
        ) as client:
            health = await client.get("/health")
            require(health.status_code == 200, "Public health endpoint failed")

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
    finally:
        await engine.dispose()


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="hist-soc-ci-release-smoke-") as directory:
        await run_smoke(Path(directory))
    print("PASS: isolated authenticated API -> PostgreSQL -> DOCX -> download smoke test")


if __name__ == "__main__":
    asyncio.run(main())
