from types import SimpleNamespace

import pytest

from app.services.source_reference_validation import validate_source_references


BASE = {
    "chunk_id": "c1",
    "source_id": "book-1",
    "source_key": "history-5",
    "url": None,
    "page_pdf_start": 12,
    "page_pdf_end": 12,
    "quote_safe": False,
}


def reference(**changes):
    values = dict(
        chunk_id="c1", source_id="book-1", source_key="history-5",
        url=None, page_pdf_start=12, page_pdf_end=12,
        page_print_start=None, page_print_end=None, quote_safe=False,
    )
    values.update(changes)
    return SimpleNamespace(**values)


def test_exact_reference_is_accepted():
    assert validate_source_references([reference()], [BASE]) == []


@pytest.mark.parametrize("change,code", [
    ({"source_id": "book-2"}, "source_id_mismatch"),
    ({"source_key": "history-6"}, "source_key_mismatch"),
    ({"url": "https://attacker.invalid"}, "url_mismatch"),
    ({"page_pdf_start": 13}, "page_pdf_start_mismatch"),
    ({"page_print_start": 13}, "page_print_start_mismatch"),
    ({"quote_safe": True}, "unsafe_quote_claim"),
])
def test_rejects_forged_metadata(change, code):
    assert code in validate_source_references([reference(**change)], [BASE])


def test_rejects_missing_chunk():
    assert "missing_or_ambiguous_chunk" in validate_source_references(
        [reference(chunk_id="absent")], [BASE]
    )


def test_rejects_ambiguous_chunk_even_with_matching_source():
    assert "missing_or_ambiguous_chunk" in validate_source_references(
        [reference()], [BASE, dict(BASE)]
    )


def test_rejects_forged_url():
    manifest = [dict(BASE, url="https://example.org/source")]
    assert "url_mismatch" in validate_source_references(
        [reference(url="https://attacker.invalid")], manifest
    )


def test_accepts_manifest_authorized_quote():
    assert validate_source_references(
        [reference(quote_safe=True)], [dict(BASE, quote_safe=True)]
    ) == []
