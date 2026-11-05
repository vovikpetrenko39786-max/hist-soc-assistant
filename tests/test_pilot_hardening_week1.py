"""Regression tests for the week-one hardening pass."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.core import pilot_auth
from app.schemas.workflow import NaturalWorkflowRequest
from app.services.natural_language_workflow import NaturalLanguageWorkflowService
from app.services.output_service import OutputRenderError, OutputService


def test_pilot_access_fails_closed_without_config(monkeypatch):
    monkeypatch.setattr(pilot_auth, "get_settings", lambda: SimpleNamespace(
        pilot_api_key=None, admin_api_key=None
    ))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pilot_auth.require_pilot_access(x_pilot_key=None, x_admin_key=None))
    assert exc.value.status_code == 503


def test_pilot_access_requires_valid_token(monkeypatch):
    monkeypatch.setattr(pilot_auth, "get_settings", lambda: SimpleNamespace(
        pilot_api_key="demo-pilot-secret", admin_api_key="demo-admin-secret"
    ))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pilot_auth.require_pilot_access(x_pilot_key="wrong", x_admin_key=None))
    assert exc.value.status_code == 401
    asyncio.run(pilot_auth.require_pilot_access(x_pilot_key="demo-pilot-secret", x_admin_key=None))
    asyncio.run(pilot_auth.require_pilot_access(x_pilot_key=None, x_admin_key="demo-admin-secret"))


@pytest.mark.asyncio
async def test_failed_quality_gate_never_exports():
    service = NaturalLanguageWorkflowService()
    service.generator.generate = AsyncMock(return_value={
        "status": "quality_failed", "run_id": "test-run-id", "quality": {"score": 20},
        "student_artifact": None,
    })
    service.output.render = AsyncMock(side_effect=AssertionError("Should not render"))
    request = NaturalWorkflowRequest(
        message="10 класс, обществознание, социальные институты. Сделай урок в Word.",
        auto_render=True, default_formats=["docx"]
    )
    result = await service.run(None, request)
    assert result["status"] == "failed"
    assert result["results"][0]["status"] == "quality_failed"
    assert result["results"][0]["files"] == []
    assert any("не прошёл проверку качества" in w for w in result["results"][0]["warnings"])
    service.output.render.assert_not_awaited()


@pytest.mark.asyncio
async def test_output_service_rejects_failed_generation():
    service = OutputService()
    fake_session = SimpleNamespace(scalar=AsyncMock(return_value=SimpleNamespace(status="quality_failed")))
    request = SimpleNamespace(generation_run_id="test", audience="teacher")
    with pytest.raises(OutputRenderError, match="not passed quality"):
        await service.render(fake_session, request)
