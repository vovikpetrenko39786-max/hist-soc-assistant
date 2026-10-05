import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.schemas.output import OutputRenderRequest, OutputRenderResponse
from app.services.output_service import OutputRenderError, OutputService
from app.services.output_templates import OutputTemplateRegistry

router = APIRouter(prefix="/outputs", tags=["outputs"])
service = OutputService()


@router.get("/templates")
async def list_templates():
    return {"templates": OutputTemplateRegistry.names()}


@router.post("/render", response_model=OutputRenderResponse)
async def render_output(
    payload: OutputRenderRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.render(session, payload)
    except (OutputRenderError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/files/{export_id}")
async def download_output(
    export_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    item = await service.get_export(session, export_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Export not found")
    path = Path(item.file_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Export file is missing from storage")
    media = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if item.file_format == "docx"
        else "application/pdf"
    )
    return FileResponse(path, filename=item.file_name, media_type=media)


@router.get("/runs/{run_id}")
async def list_run_outputs(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    rows = await service.list_run_exports(session, run_id)
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
