"""A saved next_step is required for automatic next-lesson selection."""
import uuid
from unittest.mock import AsyncMock

import pytest

from app.schemas.workflow import NaturalWorkflowRequest
from app.services.natural_language_workflow import NaturalLanguageWorkflowService

COURSE_ID = uuid.UUID("c18829c9-2538-45cd-8fbe-554c9c6ef633")

def context(next_step="Социальные институты", class_label="9-Б"):
    return {
        "class_course_id": str(COURSE_ID), "class_label": class_label,
        "grade": 9, "subject": "SOCIAL_STUDIES", "course_level": "basic",
        "last_lesson": {"topic": "Общество как система", "next_step": next_step},
        "progress": {"topic": "Общество как система"}, "homework": None,
    }

@pytest.mark.asyncio
async def test_next_lesson_uses_confirmed_next_step():
    service = NaturalLanguageWorkflowService()
    service.memory.build_class_course_context = AsyncMock(return_value=context())
    service.generator.generate = AsyncMock(return_value={
        "status": "generated", "run_id": None, "quality": {"score": 100},
        "student_artifact": None,
    })
    result = await service.run(None, NaturalWorkflowRequest(
        message="9-Б, обществознание. Подготовь следующий урок.",
        class_course_id=COURSE_ID,
    ))
    assert result["status"] == "completed"
    passed_request = service.generator.generate.await_args.args[1]
    assert passed_request.topic == "Социальные институты"
    assert passed_request.course_context["last_lesson"]["topic"] == "Общество как система"
    assert result["plan"]["topic"] == "Социальные институты"

@pytest.mark.asyncio
async def test_next_lesson_with_no_context_stops():
    service = NaturalLanguageWorkflowService()
    service.generator.generate = AsyncMock()
    result = await service.run(None, NaturalWorkflowRequest(
        message="9-Б, обществознание. Подготовь следующий урок."
    ))
    assert result["status"] == "planned"
    assert result["results"] == []
    service.generator.generate.assert_not_awaited()

@pytest.mark.asyncio
async def test_next_lesson_without_saved_next_step_stops():
    service = NaturalLanguageWorkflowService()
    service.memory.build_class_course_context = AsyncMock(return_value=context(None))
    service.generator.generate = AsyncMock()
    result = await service.run(None, NaturalWorkflowRequest(
        message="9-Б, обществознание. Подготовь следующий урок.",
        class_course_id=COURSE_ID,
    ))
    assert result["status"] == "planned"
    service.generator.generate.assert_not_awaited()

@pytest.mark.asyncio
async def test_course_class_mismatch_stops_generation():
    service = NaturalLanguageWorkflowService()
    service.memory.build_class_course_context = AsyncMock(return_value=context(class_label="9-В"))
    service.generator.generate = AsyncMock()
    result = await service.run(None, NaturalWorkflowRequest(
        message="9-Б, обществознание. Подготовь следующий урок.",
        class_course_id=COURSE_ID,
    ))
    assert "не соответствует" in result["summary"]
    service.generator.generate.assert_not_awaited()

@pytest.mark.asyncio
async def test_unknown_course_id_stops():
    service = NaturalLanguageWorkflowService()
    service.memory.build_class_course_context = AsyncMock(side_effect=LookupError("missing"))
    service.generator.generate = AsyncMock()
    result = await service.run(None, NaturalWorkflowRequest(
        message="9-Б, обществознание. Подготовь следующий урок.",
        class_course_id=COURSE_ID,
    ))
    assert "не найден" in result["summary"]
    service.generator.generate.assert_not_awaited()
