import asyncio
from types import SimpleNamespace
from uuid import UUID

import scripts.enrich_topic_card as script
from app.models.catalog import Topic


def test_enrich_topic_selects_topic_by_uuid_and_dry_runs(monkeypatch):
    topic_id = UUID("3b5a578c-4352-4ca6-bd79-19d48aed5365")

    topic = SimpleNamespace(
        id=topic_id,
        content_summary=None,
    )
    original_topic = vars(topic).copy()

    class FakeSession:
        def __init__(self):
            self.lookup = None
            self.committed = False
            self.rolled_back = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, model, key):
            self.lookup = (model, key)
            return topic

        async def commit(self):
            self.committed = True

        async def rollback(self):
            self.rolled_back = True

    session = FakeSession()

    class FakeCatalog:
        async def get_topic_card(self, current_session, current_topic_id):
            assert current_session is session
            assert current_topic_id == topic_id
            return {
                "topic": {
                    "id": str(topic_id),
                    "title": "Test topic",
                },
                "content_summary": None,
            }

    monkeypatch.setattr(script, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        script,
        "CurriculumCatalogService",
        lambda: FakeCatalog(),
    )
    monkeypatch.setattr(
        script,
        "build_topic_card_enrichment",
        lambda current_topic, card: {
            "content_summary": "Enriched summary",
        },
    )

    result = asyncio.run(
        script.enrich_topic(
            topic_id=topic_id,
            apply=False,
        )
    )

    assert result == 0
    assert session.lookup == (Topic, topic_id)
    assert session.committed is False
    assert session.rolled_back is True
    assert vars(topic) == original_topic


def test_generate_mode_saves_candidate_without_applying(
    monkeypatch,
    capsys,
    tmp_path,
):
    topic_id = UUID("3b5a578c-4352-4ca6-bd79-19d48aed5365")

    topic = SimpleNamespace(
        id=topic_id,
        content_summary=None,
    )
    original_topic = vars(topic).copy()

    card = {
        "subject": {"code": "HISTORY", "name": "История"},
        "grade": 10,
        "level": "basic",
        "topic": {"title": "Test topic", "description": None},
        "key_concepts": [
            {"term": "concept", "importance": "required"},
        ],
        "learning_outcomes": [
            {
                "type": "subject",
                "subtype": "knowledge",
                "text": "Outcome",
                "priority": 1,
            }
        ],
        "skills": [],
        "source_references": [
            {
                "source_key": "official-source",
                "title": "Official program",
                "section": None,
                "source_role": "official_program",
            }
        ],
    }

    class FakeSession:
        def __init__(self):
            self.rolled_back = False
            self.committed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, model, key):
            return topic

        async def rollback(self):
            self.rolled_back = True

        async def commit(self):
            self.committed = True

    session = FakeSession()

    class FakeCatalog:
        async def get_topic_card(self, current_session, current_topic_id):
            assert current_session is session
            assert current_topic_id == topic_id
            return card

    class FakeRetrieval:
        async def retrieve(self, current_session, request):
            assert current_session is session
            assert request.topic_id == topic_id
            assert request.subject == "HISTORY"
            assert request.grade == 10
            return {
                "query": request.query,
                "mode": request.mode,
                "strict_source": False,
                "warnings": [],
                "hits": [
                    {
                        "chunk_id": ("11111111-1111-1111-1111-111111111111"),
                        "source_id": ("22222222-2222-2222-2222-222222222222"),
                        "source_key": "official-source",
                        "source_title": "Official program",
                        "url": None,
                        "source_status": "official",
                        "section": "Test section",
                        "page_pdf_start": 1,
                        "page_pdf_end": 1,
                        "page_print_start": None,
                        "page_print_end": None,
                        "quote_safe": False,
                        "snippet": "Grounded evidence for concept and the test topic.",
                    }
                ],
            }

    class FakeProvider:
        async def generate_topic_enrichment(self, context):
            return {
                "content_summary": "Generated summary",
                "common_examples": [],
                "counterexamples": [],
                "typical_misconceptions": [],
                "essential_questions": [],
                "suitable_activities": [],
            }

    monkeypatch.setattr(script, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        script,
        "CurriculumCatalogService",
        lambda: FakeCatalog(),
    )
    monkeypatch.setattr(
        script,
        "get_generation_provider",
        lambda: FakeProvider(),
    )
    monkeypatch.setattr(
        script,
        "RetrievalService",
        lambda: FakeRetrieval(),
    )

    result = asyncio.run(
        script.enrich_topic(
            topic_id=topic_id,
            apply=False,
            generate=True,
            candidate_dir=tmp_path,
        )
    )

    assert result == 0
    assert session.committed is False
    assert session.rolled_back is True
    assert vars(topic) == original_topic

    candidate_files = list(tmp_path.glob("*.json"))
    assert len(candidate_files) == 1
    candidate = script.json.loads(candidate_files[0].read_text(encoding="utf-8"))
    assert candidate["topic_id"] == str(topic_id)
    assert candidate["topic_card_hash"] == script._topic_card_hash(card)
    assert candidate["evidence_chunk_ids"] == ["11111111-1111-1111-1111-111111111111"]
    assert candidate["proposed_patch"]["content_summary"] == "Generated summary"
    assert candidate["candidate_id"] == script._candidate_id(script._candidate_payload(candidate))
    assert candidate_files[0].name == f"{candidate['candidate_id']}.json"

    output = capsys.readouterr().out

    assert '"candidate_id"' in output
    assert '"proposed_patch"' in output
    assert '"evidence_chunk_ids"' in output
    assert '"pending_review"' in output
    assert '"generated_candidate"' in output
    assert '"source_chunk_ids"' in output
    assert "Topic was not changed" in output
