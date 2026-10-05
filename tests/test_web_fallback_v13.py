from app.services.web_knowledge import (
    OfficialDomainPolicy,
    OpenAIResponsesWebSearchClient,
    WebFallbackPolicy,
)


def test_exam_query_uses_fipi_domains():
    domains = OfficialDomainPolicy.allowed_domains(
        "Какие изменения в ЕГЭ-2027 по истории?", "HISTORY"
    )
    assert "fipi.ru" in domains
    assert "doc.fipi.ru" in domains


def test_law_query_uses_official_legal_domains():
    domains = OfficialDomainPolicy.allowed_domains(
        "Какая сейчас действует статья закона?", "SOCIAL_STUDIES"
    )
    assert "publication.pravo.gov.ru" in domains
    assert "pravo.gov.ru" in domains


def test_library_only_never_searches():
    assert WebFallbackPolicy.should_search(
        policy="library_only",
        local_retrieval={"hits": []},
        request_text="актуальные данные",
        allow_web_fallback=True,
        strict_source=False,
    ) is False


def test_strict_source_never_uses_web():
    assert WebFallbackPolicy.should_search(
        policy="official_web_first",
        local_retrieval={"hits": []},
        request_text="найди точную страницу",
        allow_web_fallback=True,
        strict_source=True,
    ) is False


def test_library_first_falls_back_when_local_empty():
    assert WebFallbackPolicy.should_search(
        policy="library_first",
        local_retrieval={"hits": []},
        request_text="обычный вопрос",
        allow_web_fallback=True,
        strict_source=False,
    ) is True


def test_official_web_first_always_searches():
    assert WebFallbackPolicy.should_search(
        policy="official_web_first",
        local_retrieval={"hits": [{"x": 1}, {"x": 2}, {"x": 3}]},
        request_text="проверь актуальные изменения",
        allow_web_fallback=True,
        strict_source=False,
    ) is True


def test_response_parser_collects_text_sources_and_citations():
    payload = {
        "output": [
            {
                "type": "web_search_call",
                "action": {
                    "sources": [
                        {"url": "https://fipi.ru/test", "title": "ФИПИ"},
                        {"url": "https://edsoo.ru/test", "title": "ЕДСОО"},
                    ]
                },
            },
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Проверенный ответ.",
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url": "https://fipi.ru/test",
                                "title": "ФИПИ",
                                "start_index": 0,
                                "end_index": 10,
                            }
                        ],
                    }
                ],
            },
        ]
    }
    text, sources, citations = OpenAIResponsesWebSearchClient._extract_response(payload)
    assert text == "Проверенный ответ."
    assert len(sources) == 2
    assert sources[0]["domain"] in {"fipi.ru", "edsoo.ru"}
    assert citations[0]["url"] == "https://fipi.ru/test"
