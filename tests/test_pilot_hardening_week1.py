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

PILOT_KEY = "pilot-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ-abcdef"
ADMIN_KEY = "admin-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ-abcdef"


def fake_request():
    return SimpleNamespace(state=SimpleNamespace())


def test_pilot_access_fails_closed_without_config(monkeypatch):
    monkeypatch.setattr(pilot_auth, "get_settings", lambda: SimpleNamespace(
        pilot_api_key=None, admin_api_key=None, telegram_allowed_user_ids=""
    ))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pilot_auth.require_pilot_access(
            fake_request(), x_pilot_key=None, x_admin_key=None, x_pilot_user_id=None
        ))
    assert exc.value.status_code == 503


def test_pilot_access_requires_valid_token(monkeypatch):
    monkeypatch.setattr(pilot_auth, "get_settings", lambda: SimpleNamespace(
        pilot_api_key=PILOT_KEY, admin_api_key=ADMIN_KEY,
        telegram_allowed_user_ids="123",
    ))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pilot_auth.require_pilot_access(
            fake_request(), x_pilot_key="wrong", x_admin_key=None, x_pilot_user_id="123"
        ))
    assert exc.value.status_code == 401
    principal = asyncio.run(pilot_auth.require_pilot_access(
        fake_request(), x_pilot_key=PILOT_KEY, x_admin_key=None, x_pilot_user_id="123"
    ))
    assert principal.external_id == "123"
    assert asyncio.run(pilot_auth.require_pilot_access(
        fake_request(), x_pilot_key=None, x_admin_key=ADMIN_KEY,
        x_pilot_user_id=None,
    )).role == "admin"


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


def test_weak_admin_key_cannot_bypass_scoped_pilot_auth(monkeypatch):
    """A short admin password must never unlock unrestricted API access."""
    monkeypatch.setattr(pilot_auth, "get_settings", lambda: SimpleNamespace(
        pilot_api_key=PILOT_KEY, admin_api_key="demo-admin-secret",
        telegram_allowed_user_ids="123",
    ))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pilot_auth.require_pilot_access(
            fake_request(), x_pilot_key=None, x_admin_key="demo-admin-secret",
            x_pilot_user_id=None,
        ))
    assert exc.value.status_code == 401


def test_strong_admin_key_still_allows_admin_without_pilot_headers(monkeypatch):
    monkeypatch.setattr(pilot_auth, "get_settings", lambda: SimpleNamespace(
        pilot_api_key=None, admin_api_key=ADMIN_KEY,
        telegram_allowed_user_ids="",
    ))
    principal = asyncio.run(pilot_auth.require_pilot_access(
        fake_request(), x_pilot_key=None, x_admin_key=ADMIN_KEY,
        x_pilot_user_id=None,
    ))
    assert principal.role == "admin"


@pytest.mark.parametrize("module_name,guard_name", [
    ("app.api.routes.admin_library", "_admin"),
    ("app.api.routes.pilot", "_require_admin"),
])
def test_legacy_admin_routes_reject_weak_config(monkeypatch, module_name, guard_name):
    """Legacy admin endpoints must not bypass the shared admin-key strength guard."""
    import importlib

    module = importlib.import_module(module_name)
    monkeypatch.setattr(module, "settings", SimpleNamespace(admin_api_key="demo-admin-secret"))
    with pytest.raises(HTTPException) as exc:
        getattr(module, guard_name)("demo-admin-secret")
    assert exc.value.status_code == 503


@pytest.mark.parametrize("module_name,guard_name", [
    ("app.api.routes.admin_library", "_admin"),
    ("app.api.routes.pilot", "_require_admin"),
])
def test_legacy_admin_routes_require_correct_strong_key(monkeypatch, module_name, guard_name):
    import importlib

    module = importlib.import_module(module_name)
    monkeypatch.setattr(module, "settings", SimpleNamespace(admin_api_key=ADMIN_KEY))
    with pytest.raises(HTTPException) as exc:
        getattr(module, guard_name)("incorrect-key")
    assert exc.value.status_code == 401
    assert getattr(module, guard_name)(ADMIN_KEY) is None
