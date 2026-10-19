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


def test_generate_mode_uses_provider_and_rolls_back(monkeypatch):
    topic_id = UUID("3b5a578c-4352-4ca6-bd79-19d48aed5365")

    topic = SimpleNamespace(
        id=topic_id,
        content_summary=None,
    )

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

    result = asyncio.run(
        script.enrich_topic(
            topic_id=topic_id,
            apply=False,
            generate=True,
        )
    )

    assert result == 0
    assert session.rolled_back is True
    assert session.committed is False
    assert topic.content_summary is None
