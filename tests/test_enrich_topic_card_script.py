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
    assert topic.content_summary == "Enriched summary"
