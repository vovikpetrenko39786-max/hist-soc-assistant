from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import ExportedFile, GenerationRun
from app.services.docx_renderer import DocxArtifactRenderer
from app.services.output_templates import OutputTemplateRegistry
from app.services.pdf_export import PdfExporter, PdfExportError

settings = get_settings()


class OutputRenderError(RuntimeError):
    pass


def _slug(text: str) -> str:
    text = re.sub(r"[^\w\-]+", "_", text.strip(), flags=re.UNICODE)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:120] or "material"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class OutputService:
    async def render(self, session: AsyncSession, request) -> dict:
        run = None
        if request.generation_run_id:
            run = await session.scalar(
                select(GenerationRun).where(GenerationRun.id == request.generation_run_id)
            )
            if run is None:
                raise OutputRenderError("Generation run not found")
            bundle = run.output_json or {}
            artifact = bundle.get(request.audience)
            if not artifact:
                raise OutputRenderError(
                    f"Generation run has no '{request.audience}' artifact"
                )
            artifact_type = run.task_type
        else:
            artifact = request.artifact
            artifact_type = request.artifact_type or artifact.get("artifact_type")
            if not artifact_type:
                raise OutputRenderError("artifact_type is required for inline artifact")

        template = OutputTemplateRegistry.get(request.template_name)
        base = request.filename_base or artifact.get("title") or artifact_type
        audience_suffix = "teacher" if request.audience == "teacher" else "student"
        stem = f"{_slug(base)}_{audience_suffix}"

        run_part = str(run.id) if run else "inline"
        out_dir = Path(settings.output_storage_dir) / run_part
        out_dir.mkdir(parents=True, exist_ok=True)

        renderer = DocxArtifactRenderer(template)
        files = []
        warnings = []

        docx_path = out_dir / f"{stem}.docx"
        need_docx = "docx" in request.formats or "pdf" in request.formats
        if need_docx:
            renderer.render(artifact, request.audience, docx_path)

        paths: dict[str, Path] = {}
        if "docx" in request.formats:
            paths["docx"] = docx_path
        if "pdf" in request.formats:
            pdf_path = out_dir / f"{stem}.pdf"
            try:
                PdfExporter().convert_docx(docx_path, pdf_path)
                paths["pdf"] = pdf_path
            except PdfExportError as exc:
                warnings.append(str(exc))
                if request.formats == ["pdf"]:
                    raise OutputRenderError(str(exc)) from exc

        for fmt, path in paths.items():
            sha = _sha256(path)
            size = path.stat().st_size
            row = ExportedFile(
                generation_run_id=run.id if run else None,
                artifact_type=artifact_type,
                audience=request.audience,
                file_format=fmt,
                template_name=template.name,
                template_version=template.version,
                file_path=str(path),
                file_name=path.name,
                sha256=sha,
                size_bytes=size,
                status="ready",
                metadata_json={
                    "source": "generation_run" if run else "inline",
                    "font": template.font_name,
                },
            )
            session.add(row)
            await session.flush()
            files.append({
                "export_id": row.id,
                "file_name": path.name,
                "file_format": fmt,
                "audience": request.audience,
                "template_name": template.name,
                "template_version": template.version,
                "size_bytes": size,
                "sha256": sha,
                "file_path": str(path),
                "download_path": f"/api/v1/outputs/files/{row.id}",
            })

        if "docx" not in request.formats and "pdf" in paths and not settings.output_keep_intermediate_docx_for_pdf:
            docx_path.unlink(missing_ok=True)

        await session.commit()
        return {
            "artifact_type": artifact_type,
            "audience": request.audience,
            "files": files,
            "warnings": warnings,
        }

    async def get_export(self, session: AsyncSession, export_id: uuid.UUID) -> ExportedFile | None:
        return await session.scalar(
            select(ExportedFile).where(ExportedFile.id == export_id)
        )

    async def list_run_exports(self, session: AsyncSession, run_id: uuid.UUID):
        rows = await session.execute(
            select(ExportedFile)
            .where(ExportedFile.generation_run_id == run_id)
            .order_by(ExportedFile.created_at)
        )
        return list(rows.scalars().all())
