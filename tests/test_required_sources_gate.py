from app.services.pedagogy_quality import PedagogyQualityGate
from app.schemas.pedagogy import PedagogyGenerationRequest
from app.services.generation_context import GroundedContextBuilder
from app.services.pedagogy_provider import source_refs


def _check(report, code):
    return next(x for x in report["checks"] if x["code"] == code)


def test_required_sources_empty_manifest_fails():
    gate = PedagogyQualityGate()

    teacher = {
        "artifact_type": "informational",
        "answer": (
            "Без подтвержденных официальных материалов нельзя достоверно "
            "перечислить изменения."
        ),
        "source_references": [],
    }

    report = gate.evaluate(
        "informational",
        teacher,
        None,
        None,
        [],
        require_sources=True,
    )

    assert report["passed"] is False

    check = _check(report, "required_sources")
    assert check["passed"] is False
    assert "source_manifest пуст" in check["message"]


def test_non_strict_informational_can_have_empty_manifest():
    gate = PedagogyQualityGate()

    teacher = {
        "artifact_type": "informational",
        "answer": "Краткий аналитический ответ без заявленных внешних источников.",
        "source_references": [],
    }

    report = gate.evaluate(
        "informational",
        teacher,
        None,
        None,
        [],
        require_sources=False,
    )

    assert "required_sources" not in {
        x["code"] for x in report["checks"]
    }


def test_required_sources_with_manifest_passes_source_requirement():
    gate = PedagogyQualityGate()

    title = "ФИПИ. ЕГЭ-2027. История. Демонстрационный вариант (проект)"

    manifest = [
        {
            "chunk_id": "test-fipi-2027-001",
            "source_id": "test-fipi-2027",
            "source_key": "fipi-ege-history-2027-demo",
            "title": title,
            "source_title": title,
            "page_pdf_start": 1,
            "page_pdf_end": 1,
            "page_print_start": 3,
            "page_print_end": 3,
            "status": "project",
        }
    ]

    teacher = {
        "artifact_type": "informational",
        "answer": (
            "Материал ФИПИ на 2027 год обозначен как проект. "
            "Сведения основаны на указанном документе."
        ),
        "source_references": [
            {
                "chunk_id": "test-fipi-2027-001",
                "source_id": "test-fipi-2027",
                "source_key": "fipi-ege-history-2027-demo",
                "title": title,
                "source_title": title,
                "page_pdf_start": 1,
                "page_pdf_end": 1,
                "page_print_start": 3,
                "page_print_end": 3,
            }
        ],
    }

    report = gate.evaluate(
        "informational",
        teacher,
        None,
        None,
        manifest,
        require_sources=True,
    )

    check = _check(report, "required_sources")
    assert check["passed"] is True


def _context(library=None, web=None):
    request = PedagogyGenerationRequest(
        artifact_type="informational",
        subject="HISTORY",
        request_text="Что изменилось в ЕГЭ-2027 по истории?",
    )
    return GroundedContextBuilder().build(request, None, library or {"hits": []}, web)


def test_library_manifest_only_is_unchanged():
    library_hit = {
        "chunk_id": "library-chunk",
        "source_id": "library-source",
        "source_key": "FIPI-2027",
        "source_title": "ФИПИ. Демонстрационный вариант ЕГЭ-2027",
        "source_status": "project",
        "page_pdf_start": 4,
        "page_pdf_end": 4,
        "page_print_start": 6,
        "page_print_end": 6,
    }

    manifest = _context({"hits": [library_hit]})["source_manifest"]

    assert len(manifest) == 1
    assert manifest[0]["chunk_id"] == "library-chunk"
    assert manifest[0]["page_pdf_start"] == 4


def test_web_only_source_enters_manifest_and_passes_informational_gate():
    context = _context(web={"sources": [{"url": "https://fipi.ru/ege/history/demo", "title": "ФИПИ: проект ЕГЭ-2027 по истории"}]})
    manifest = context["source_manifest"]
    refs = source_refs(manifest)
    report = PedagogyQualityGate().evaluate(
        "informational",
        {"answer": "Документ опубликован как проект.", "source_references": refs},
        None,
        None,
        manifest,
        require_sources=True,
    )

    assert manifest[0]["origin"] == "web"
    assert manifest[0]["chunk_id"] == refs[0]["chunk_id"]
    assert refs[0]["url"] == manifest[0]["url"]
    assert _check(report, "required_sources")["passed"]
    assert _check(report, "source_subset")["passed"]


def test_same_url_source_and_citation_merge_indexes_without_losing_source_metadata():
    url = "https://fipi.ru/ege/history/demo"
    context = _context(web={
        "sources": [{
            "url": url,
            "title": "Официальное название документа",
            "start_index": None,
            "end_index": None,
        }],
        "citations": [{
            "url": url,
            "title": "Название из citation",
            "start_index": 12,
            "end_index": 34,
        }],
    })
    manifest = context["source_manifest"]
    refs = source_refs(manifest)
    report = PedagogyQualityGate().evaluate(
        "informational",
        {"answer": "Документ опубликован как проект.", "source_references": refs},
        None,
        None,
        manifest,
        require_sources=True,
    )

    assert len(manifest) == 1
    assert manifest[0]["title"] == "Официальное название документа"
    assert manifest[0]["start_index"] == 12
    assert manifest[0]["end_index"] == 34
    assert refs[0]["chunk_id"] == manifest[0]["chunk_id"]
    assert refs[0]["url"] == url
    assert _check(report, "source_subset")["passed"]


def test_empty_library_and_web_keep_strict_informational_failed():
    context = _context(web={"performed": True, "sources": [], "citations": []})
    report = PedagogyQualityGate().evaluate(
        "informational",
        {"answer": "Нет подтвержденных сведений.", "source_references": []},
        None,
        None,
        context["source_manifest"],
        require_sources=True,
    )

    assert report["passed"] is False
    assert _check(report, "required_sources")["passed"] is False


def test_web_indices_do_not_become_pages_and_page_grounding_skips_unknown_pages():
    context = _context(web={"sources": [{
        "url": "https://fipi.ru/ege/history/demo",
        "title": "Проект демоверсии",
        "start_index": 15,
        "end_index": 42,
    }]})
    manifest = context["source_manifest"]
    ref = source_refs(manifest)[0]
    report = PedagogyQualityGate().evaluate(
        "informational",
        {"answer": "Документ опубликован как проект.", "source_references": [ref]},
        None,
        None,
        manifest,
        require_sources=True,
    )

    assert manifest[0]["start_index"] == 15
    assert manifest[0]["end_index"] == 42
    assert not any(field in manifest[0] for field in (
        "page_pdf_start", "page_pdf_end", "page_print_start", "page_print_end"
    ))
    assert _check(report, "page_grounding")["passed"]


def test_duplicate_web_source_keeps_library_chunk_and_page_metadata():
    library_hit = {
        "chunk_id": "library-chunk",
        "source_id": "library-source",
        "source_key": "FIPI-2027",
        "source_title": "ФИПИ: проект ЕГЭ-2027 по истории",
        "source_status": "project",
        "url": "https://fipi.ru/ege/history/demo",
        "page_pdf_start": 7,
        "page_pdf_end": 8,
        "page_print_start": 9,
        "page_print_end": 10,
    }
    web = {"sources": [{
        "url": library_hit["url"],
        "title": library_hit["source_title"],
        "page_pdf_start": 99,
        "page_print_start": 99,
        "start_index": 3,
    }]}

    manifest = _context({"hits": [library_hit]}, web)["source_manifest"]

    assert len(manifest) == 1
    assert manifest[0]["chunk_id"] == "library-chunk"
    assert manifest[0]["source_id"] == "library-source"
    assert manifest[0]["page_pdf_start"] == 7
    assert manifest[0]["page_print_start"] == 9


def test_generated_web_chunk_id_is_stable():
    web = {"sources": [{
        "url": "https://fipi.ru/ege/history/demo",
        "title": "Проект демоверсии",
        "start_index": 15,
        "end_index": 42,
    }]}

    first = _context(web=web)["source_manifest"][0]["chunk_id"]
    second = _context(web=web)["source_manifest"][0]["chunk_id"]

    assert first == second


def test_manifest_entry_without_source_identity_does_not_satisfy_gate():
    report = PedagogyQualityGate().evaluate(
        "informational",
        {"answer": "Текст без подтверждения.", "source_references": []},
        None,
        None,
        [{"chunk_id": "orphan-chunk", "title": "Без source ID и URL"}],
        require_sources=True,
    )

    assert report["passed"] is False
    assert _check(report, "required_sources")["passed"] is False
