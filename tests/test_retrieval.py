import asyncio
import uuid

import pytest

from app.schemas.retrieval import RetrievalRequest
from app.services.embeddings import HashEmbeddingProvider
from app.services.retrieval import Candidate, RetrievalService


class DummySource:
    def __init__(self, status="primary", authority_rank=90, is_current=True):
        self.id = uuid.uuid4()
        self.status = status
        self.authority_rank = authority_rank
        self.is_current = is_current
        self.source_key = "TEST"
        self.title = "Test source"
        self.source_type = "textbook"
        self.origin = "teacher_upload"


class DummyChunk:
    def __init__(self, text="Социальный институт имеет признаки устойчивости."):
        self.id = uuid.uuid4()
        self.text = text
        self.section = "§ 1"
        self.page_pdf = 10
        self.page_pdf_end = 10
        self.page_print = 8
        self.page_print_end = 8
        self.embedding_model = "hash-384-v1"


def test_hash_embeddings_are_deterministic_and_normalized():
    provider = HashEmbeddingProvider(dim=384)
    a = asyncio.run(provider.embed_query("социальные институты"))
    b = asyncio.run(provider.embed_query("социальные институты"))
    assert a == b
    assert len(a) == 384
    norm = sum(v * v for v in a) ** 0.5
    assert abs(norm - 1.0) < 1e-9


def test_strict_source_requires_source():
    with pytest.raises(ValueError):
        RetrievalRequest(query="социальный институт", strict_source=True)


def test_exact_score_beats_non_exact():
    service = RetrievalService()
    request = RetrievalRequest(
        query="социальный институт",
        mode="hybrid",
        exact_phrase="социальный институт",
    )
    source = DummySource()
    exact = Candidate(
        chunk=DummyChunk("Социальный институт — устойчивый элемент общества."),
        source=source, lexical_rank=1, vector_rank=1, exact_match=True,
    )
    non_exact = Candidate(
        chunk=DummyChunk("Общественные институты выполняют важные функции."),
        source=source, lexical_rank=1, vector_rank=1, exact_match=False,
    )
    assert service._final_score(exact, request) > service._final_score(non_exact, request)


def test_quote_safe_only_for_exact_phrase_hit():
    service = RetrievalService()
    candidate = Candidate(
        chunk=DummyChunk("Социальный институт — устойчивый элемент общества."),
        source=DummySource(), lexical_rank=1, exact_match=True, final_score=0.9,
    )
    request = RetrievalRequest(
        query="социальный институт",
        mode="exact",
        exact_phrase="социальный институт",
    )
    hit = service._serialize_hit(candidate, request)
    assert hit["quote_safe"] is True
    assert hit["page_reference_status"] == "verified_print_and_pdf"


def test_snippet_contains_exact_phrase():
    service = RetrievalService()
    text = ("Введение. " * 50) + "Социальный институт имеет ряд признаков." + (" Конец." * 50)
    snippet = service._snippet(
        text, "социальный институт", "социальный институт", max_chars=180
    )
    assert "Социальный институт" in snippet
    assert len(snippet) <= 182
