"""Explicit source selection can never silently fall back to other books/web."""
from unittest.mock import AsyncMock

import pytest

from app.schemas.workflow import NaturalWorkflowRequest
from app.services.natural_language_workflow import (
    NaturalLanguageParser,
    NaturalLanguageWorkflowService,
)


def _plan(message, source_key=None):
    return NaturalLanguageParser().parse(NaturalWorkflowRequest(
        message=message, source_key=source_key,
    ))


def test_source_key_implies_strict_library_only():
    plan = _plan("10 класс, обществознание. Сделай урок: социальные институты.", "  TEST-BOOK-1  ")
    assert plan.strict_source is True
    assert plan.source_key == "TEST-BOOK-1"
    assert plan.knowledge_policy == "library_only"
    assert plan.web_fallback_allowed is False


def test_explicit_web_request_cannot_override_selected_source():
    plan = _plan("10 класс, история. Проверь в интернете тему и сделай урок: реформы.", "BOOK-1")
    assert plan.strict_source is True
    assert plan.knowledge_policy == "library_only"
    assert plan.web_fallback_allowed is False


def test_unselected_source_keeps_default_workflow():
    plan = _plan("10 класс, обществознание. Сделай урок: социальные институты.")
    assert plan.strict_source is False
    assert plan.source_key is None


def test_whitespace_key_is_not_an_explicit_selection():
    plan = _plan("10 класс, обществознание. Сделай урок: социальные институты.", "  ")
    assert plan.strict_source is False
    assert plan.source_key is None


@pytest.mark.asyncio
async def test_generation_receives_strict_source_and_no_web_fallback():
    svc = NaturalLanguageWorkflowService()
    svc.generator.generate = AsyncMock(return_value={
        "status": "generated", "run_id": None, "quality": {"score": 100},
        "student_artifact": None,
    })
    result = await svc.run(None, NaturalWorkflowRequest(
        message="10 класс, обществознание. Сделай урок: социальные институты.",
        source_key="BOOK-1",
        auto_render=False,
    ))
    assert result["status"] == "completed"
    req = svc.generator.generate.await_args.args[1]
    assert req.source_key == "BOOK-1"
    assert req.strict_source is True
    assert req.allow_web_fallback is False
