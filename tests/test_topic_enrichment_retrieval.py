import asyncio
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.retrieval import RetrievalRequest
from app.services.retrieval import RetrievalService
from app.services.topic_enrichment_retrieval import retrieve_topic_enrichment


def test_concept_queries_are_bounded_deduplicated_and_scoped():
    requests = []
    topic_id = UUID("11111111-1111-1111-1111-111111111111")
    class Retriever:
        async def retrieve(self, session, request):
            requests.append(request)
            return {"hits": [{"chunk_id": "same"}, {"chunk_id": request.query}],
                    "warnings": ["embedding unavailable"]}
    card = {"topic": {"title": "Title"}, "subject": {"code": "HISTORY"},
            "grade": 5, "level": "basic", "key_concepts": [
                {"term": x} for x in ["Title", "", "A", "B", "C", "D"]]}
    result = asyncio.run(retrieve_topic_enrichment(None, card, topic_id, Retriever()))
    assert [r.query for r in requests] == ["Title", "A", "B", "C"]
    assert all(r.topic_id == topic_id and r.grade == 5 and r.subject == "HISTORY"
               and r.level == "basic" and r.snippet_chars == 2400 for r in requests)
    assert len(result["hits"]) == 5
    assert result["warnings"] == ["embedding unavailable"]


def test_extended_snippet_preserves_explanation_and_default_stays_short():
    text = "Тема. " + "содержание " * 80 + "Объяснение понятия."
    assert "Объяснение" not in RetrievalService._snippet(text, "Тема")
    assert "Объяснение" in RetrievalService._snippet(text, "Тема", max_chars=2400)
    assert RetrievalRequest(query="Тема").snippet_chars == 520


@pytest.mark.parametrize("size", [199, 4001])
def test_snippet_budget_is_bounded(size):
    with pytest.raises(ValidationError):
        RetrievalRequest(query="Тема", snippet_chars=size)
