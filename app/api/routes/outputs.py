import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import get_settings
from app.core.pilot_auth import require_user_principal
from app.models.entities import ExportedFile, GenerationRun
from app.schemas.output import OutputRenderRequest, OutputRenderResponse
from app.services.export_integrity import (
    ExportIntegrityError,
    storage_roots,
    verified_export_path_in_roots,
)
from app.services.output_service import OutputRenderError, OutputService
from app.services.output_templates import OutputTemplateRegistry

router = APIRouter(prefix="/outputs", tags=["outputs"])
service = OutputService()


async def authorize_export(
    request: Request,
    session: AsyncSession,
    item: ExportedFile,
) -> None:
    """Legacy/unowned exports are admin-only; users see only their own runs."""
    principal = require_user_principal(request)
    if principal.role == "admin":
        return
    if not item.generation_run_id:
        raise HTTPException(status_code=404, detail="Export not found")
    run = await session.get(GenerationRun, item.generation_run_id)
    owner = (run.request_json or {}).get("_owner_principal") if run else None
    if owner != f"telegram:{principal.external_id}":
        raise HTTPException(status_code=404, detail="Export not found")


@router.get("/templates")
async def list_templates():
    return {"templates": OutputTemplateRegistry.names()}


@router.post("/render", response_model=OutputRenderResponse)
async def render_output(
    payload: OutputRenderRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    principal = require_user_principal(request)
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="Direct export rendering is admin-only")
    try:
        return await service.render(session, payload)
    except (OutputRenderError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/files/{export_id}")
async def download_output(
    export_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    item = await service.get_export(session, export_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Export not found")
    await authorize_export(request, session, item)
    try:
        settings = get_settings()
        path = verified_export_path_in_roots(
            item.file_path,
            storage_roots(
                settings.output_storage_dir,
                settings.output_legacy_storage_roots_json,
            ),
            item.size_bytes,
            item.sha256,
        )
    except ExportIntegrityError as exc:
        if exc.reason == "invalid_roots":
            raise HTTPException(status_code=503, detail="Export storage is misconfigured") from exc
        if exc.reason == "outside_root":
            raise HTTPException(status_code=403, detail="Export path rejected") from exc
        if exc.reason == "missing":
            raise HTTPException(status_code=410, detail="Export file is missing") from exc
        raise HTTPException(status_code=409, detail="Export file integrity check failed") from exc
    media = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if item.file_format == "docx"
        else "application/pdf"
    )
    return FileResponse(path, filename=item.file_name, media_type=media)


@router.get("/runs/{run_id}")
async def list_run_outputs(
    run_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    rows = await service.list_run_exports(session, run_id)
    for row in rows:
        await authorize_export(request, session, row)
    return [
        {
            "export_id": str(x.id),
            "file_name": x.file_name,
            "file_format": x.file_format,
            "audience": x.audience,
            "template_name": x.template_name,
            "template_version": x.template_version,
            "size_bytes": x.size_bytes,
            "sha256": x.sha256,
            "download_path": f"/api/v1/outputs/files/{x.id}",
        }
        for x in rows
    ]
