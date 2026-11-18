from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.workflow import NaturalWorkflowRequest
from app.services.natural_language_workflow import NaturalLanguageWorkflowService
from app.services.output_service import OutputRenderError, OutputService


@pytest.mark.asyncio
async def test_failed_quality_gate_never_exports():
    service = NaturalLanguageWorkflowService()
    service.generator.generate = AsyncMock(return_value={
        "status": "quality_failed",
        "run_id": "test-run-id",
        "quality": {"score": 20},
        "student_artifact": None,
    })
    service.output.render = AsyncMock(side_effect=AssertionError("must not render"))
    request = NaturalWorkflowRequest(
        message="10 класс, обществознание, социальные институты. Сделай урок в Word.",
        auto_render=True,
        default_formats=["docx"],
    )

    result = await service.run(None, request)

    assert result["status"] == "failed"
    assert result["results"][0]["status"] == "quality_failed"
    assert result["results"][0]["files"] == []
    assert any(
        "не прошёл проверку качества" in warning
        for warning in result["results"][0]["warnings"]
    )
    service.output.render.assert_not_awaited()


@pytest.mark.asyncio
async def test_output_service_rejects_failed_generation():
    service = OutputService()
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=SimpleNamespace(status="quality_failed"))
    )
    request = SimpleNamespace(generation_run_id="test", audience="teacher")

    with pytest.raises(OutputRenderError, match="not passed quality"):
        await service.render(session, request)
