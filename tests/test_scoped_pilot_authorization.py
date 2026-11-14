"""Pilot users cannot cross course or export ownership boundaries."""
import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import workflow as workflow_route
from app.api.routes.outputs import authorize_export
from app.api.routes.pilot import create_feedback
from app.core import pilot_auth
from app.core.pilot_auth import PilotPrincipal
from app.schemas.pilot import PilotFeedbackCreate
from app.schemas.workflow import NaturalWorkflowRequest
from app.services.natural_language_workflow import NaturalLanguageWorkflowService
from telegram_bot.api_client import TeacherAssistantApi

PILOT_KEY = "pilot-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ-abcdef"
COURSE_ID = uuid.UUID("c18829c9-2538-45cd-8fbe-554c9c6ef633")
OTHER_COURSE_ID = uuid.UUID("7621fc88-8e26-4d0e-bb06-62a0fb3a1cca")


def settings():
    return SimpleNamespace(
        pilot_api_key=PILOT_KEY,
        admin_api_key="admin-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ-abcdef",
        telegram_allowed_user_ids="123,456",
        telegram_course_bindings_json=(
            '{"123":{"9b":{"class_course_id":"' + str(COURSE_ID) + '"}},'
            '"456":{"10a":{"class_course_id":"' + str(OTHER_COURSE_ID) + '"}}}'
        ),
    )


def request():
    return SimpleNamespace(state=SimpleNamespace())


async def authenticate(monkeypatch, user_id="123"):
    monkeypatch.setattr(pilot_auth, "get_settings", settings)
    req = request()
    await pilot_auth.require_pilot_access(
        req,
        x_pilot_key=PILOT_KEY,
        x_admin_key=None,
        x_pilot_user_id=user_id,
    )
    return req


def test_course_binding_allows_only_the_authenticated_user(monkeypatch):
    req = asyncio.run(authenticate(monkeypatch))
    assert pilot_auth.authorize_course(req, COURSE_ID).external_id == "123"
    with pytest.raises(HTTPException) as exc:
        pilot_auth.authorize_course(req, OTHER_COURSE_ID)
    assert exc.value.status_code == 403


def test_unlisted_user_is_rejected_before_course_access(monkeypatch):
    monkeypatch.setattr(pilot_auth, "get_settings", settings)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pilot_auth.require_pilot_access(
            request(), x_pilot_key=PILOT_KEY, x_admin_key=None,
            x_pilot_user_id="999",
        ))
    assert exc.value.status_code == 403


def test_weak_runtime_key_fails_closed(monkeypatch):
    weak = settings()
    weak.pilot_api_key = "short"
    monkeypatch.setattr(pilot_auth, "get_settings", lambda: weak)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pilot_auth.require_pilot_access(
            request(), x_pilot_key="short", x_admin_key=None,
            x_pilot_user_id="123",
        ))
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_export_owner_is_enforced(monkeypatch):
    req = await authenticate(monkeypatch)
    item = SimpleNamespace(generation_run_id=uuid.uuid4())
    own_run = SimpleNamespace(request_json={"_owner_principal": "telegram:123"})
    session = SimpleNamespace(get=lambda model, identifier: _async_value(own_run))
    await authorize_export(req, session, item)

    other_run = SimpleNamespace(request_json={"_owner_principal": "telegram:456"})
    session = SimpleNamespace(get=lambda model, identifier: _async_value(other_run))
    with pytest.raises(HTTPException) as exc:
        await authorize_export(req, session, item)
    assert exc.value.status_code == 404


async def _async_value(value):
    return value


def test_telegram_client_attaches_user_scope_header():
    client = TeacherAssistantApi("http://backend", api_key=PILOT_KEY)
    assert client.user_headers(123) == {
        "X-Pilot-Key": PILOT_KEY,
        "X-Pilot-User-ID": "123",
    }


@pytest.mark.asyncio
async def test_telegram_health_uses_protected_pilot_endpoint(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True, "release": "test"}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, *, headers):
            captured["url"] = url
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("telegram_bot.api_client.httpx.AsyncClient", FakeAsyncClient)
    client = TeacherAssistantApi("http://backend", api_key=PILOT_KEY)

    assert await client.health(123) == {"ok": True, "release": "test"}
    assert captured["url"] == "http://backend/api/v1/pilot/health"
    assert captured["headers"] == {
        "X-Pilot-Key": PILOT_KEY,
        "X-Pilot-User-ID": "123",
    }


@pytest.mark.asyncio
async def test_feedback_identity_comes_from_authenticated_principal():
    class FakeSession:
        row = None

        def add(self, row):
            self.row = row

        async def commit(self):
            return None

        async def refresh(self, row):
            row.id = uuid.uuid4()

    session = FakeSession()
    req = SimpleNamespace(
        state=SimpleNamespace(pilot_principal=PilotPrincipal("pilot_user", "123"))
    )
    payload = PilotFeedbackCreate(
        text="test",
        user_external_id="456",
    )

    await create_feedback(payload, req, session)

    assert session.row.user_external_id == "123"


@pytest.mark.asyncio
async def test_workflow_preserves_course_authorization_error(monkeypatch):
    monkeypatch.setattr(
        workflow_route,
        "require_user_principal",
        lambda request: PilotPrincipal("pilot_user", "123"),
    )

    def deny_course(request, class_course_id):
        raise HTTPException(status_code=403, detail="Course access denied")

    monkeypatch.setattr(workflow_route, "authorize_course", deny_course)
    payload = NaturalWorkflowRequest(
        message="Подготовь урок",
        class_course_id=COURSE_ID,
    )

    with pytest.raises(HTTPException) as exc:
        await workflow_route.run(payload, request(), SimpleNamespace())

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_workflow_records_authenticated_export_owner():
    run = SimpleNamespace(request_json={}, class_course_id=None, teacher_id=None)
    session = SimpleNamespace(
        get=lambda model, identifier: _async_value(run),
        commit=lambda: _async_value(None),
    )
    service = NaturalLanguageWorkflowService()
    service.generator.generate = _async_callable({
        "status": "generated",
        "run_id": uuid.uuid4(),
        "quality": {"score": 100},
        "student_artifact": None,
    })
    result = await service.run(
        session,
        NaturalWorkflowRequest(
            message="10 класс, обществознание, социальные институты. Сделай урок.",
            auto_render=False,
        ),
        owner_principal="telegram:123",
    )
    assert result["status"] == "completed"
    assert run.request_json["_owner_principal"] == "telegram:123"


def _async_callable(value):
    async def call(*args, **kwargs):
        return value
    return call
