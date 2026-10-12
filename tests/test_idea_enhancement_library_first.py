import asyncio
from unittest.mock import AsyncMock

from app.schemas.pedagogy import PedagogyGenerationRequest
from app.services.pedagogy_generation import PedagogyGenerationService


def test_idea_enhancement_library_first_retrieves_sources():
    """
    Regression test.

    Informational / analytical requests may be routed as idea_enhancement.
    With library_first they must still search the local RAG library and
    pass retrieved chunks into source_manifest.
    """

    async def scenario():
        service = PedagogyGenerationService()

        fake_hit = {
            "chunk_id": "chunk-test-1",
            "source_id": "source-test-1",
            "source_key": "FIPI_EGE_2027_HISTORY_DEMO",
            "source_title": "ФИПИ. ЕГЭ-2027. История. Демонстрационный вариант (проект)",
            "source_type": "exam_document",
            "source_status": "official",
            "section": "Демонстрационный вариант",
            "page_pdf_start": 1,
            "page_pdf_end": 1,
            "page_print_start": 3,
            "page_print_end": 3,
            "quote_safe": True,
            "snippet": "Тестовый фрагмент официального документа ФИПИ.",
            "final_score": 1.0,
        }

        # Для idea_enhancement начальный topic-based retrieval не выполняется.
        # Новый fallback обязан выполнить поиск по полному тексту запроса.
        service.retrieval.retrieve = AsyncMock(
            return_value={
                "query": "Что изменилось в ЕГЭ-2027 по истории?",
                "mode": "hybrid",
                "hits": [fake_hit],
                "warnings": [],
            }
        )

        # Интернет в этом тесте нам не нужен.
        service.web.controlled_fallback = AsyncMock(
            return_value={
                "performed": False,
                "planned": False,
                "policy": "library_first",
                "scope": None,
                "answer": None,
                "sources": [],
                "citations": [],
                "allowed_domains": [],
                "search_run_id": None,
            }
        )

        request = PedagogyGenerationRequest(
            artifact_type="idea_enhancement",
            request_text=(
                "Что изменилось в ЕГЭ-2027 по истории? "
                "Подготовь краткую памятку для учителя."
            ),
            subject="HISTORY",
            grade=11,
            level="exam",
            audience="teacher",
            knowledge_policy="library_first",
            allow_web_fallback=False,
            strict_source=False,
            dry_run=True,
            save_run=False,
        )

        result = await service.generate(object(), request)

        assert result["status"] == "dry_run"

        retrieval = result["retrieval"]
        context = result["generation_context"]

        assert len(retrieval["hits"]) == 1
        assert len(context["source_manifest"]) == 1

        source = context["source_manifest"][0]

        assert source["source_id"] == "source-test-1"
        assert source["title"].startswith("ФИПИ. ЕГЭ-2027")
        assert source["page_pdf_start"] == 1
        assert source["page_print_start"] == 3

        # Самое важное: fallback действительно был вызван.
        service.retrieval.retrieve.assert_awaited_once()

        retrieval_request = service.retrieval.retrieve.await_args.args[1]

        assert retrieval_request.query == request.request_text
        assert retrieval_request.subject == "HISTORY"
        assert retrieval_request.grade == 11
        assert retrieval_request.level == "exam"
        assert retrieval_request.mode == "hybrid"
        assert retrieval_request.top_k == 8

    asyncio.run(scenario())
