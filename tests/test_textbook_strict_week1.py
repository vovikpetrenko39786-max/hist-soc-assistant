"""Strict textbook requests never silently broaden their source scope."""
import pytest

from app.schemas.workflow import NaturalWorkflowRequest
from app.services.natural_language_workflow import (
    NaturalLanguageParser,
    NaturalLanguageWorkflowService,
)


def test_explicit_textbook_mode_uses_library_only_and_selected_key():
    plan = NaturalLanguageParser().parse(NaturalWorkflowRequest(
        message="10 класс, обществознание, социальные институты. Сделай урок только по учебнику.",
        source_key="BOOK-TEST",
    ))
    assert plan.strict_source is True
    assert plan.source_key == "BOOK-TEST"
    assert plan.knowledge_policy == "library_only"
    assert plan.web_fallback_allowed is False


@pytest.mark.asyncio
async def test_strict_textbook_without_key_stops_before_generation():
    workflow = NaturalLanguageWorkflowService()
    result = await workflow.run(None, NaturalWorkflowRequest(
        message="10 класс, обществознание, социальные институты. Сделай урок только по учебнику."
    ))
    assert result["status"] == "planned"
    assert result["results"] == []
    assert "source_key" in result["summary"]
