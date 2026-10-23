import asyncio
import json
from types import SimpleNamespace
from uuid import UUID

import pytest

import scripts.enrich_topic_card as script
from app.models.catalog import Topic
from app.services.topic_enrichment_generation import TopicEnrichmentGenerationError

TOPIC_ID = UUID("3b5a578c-4352-4ca6-bd79-19d48aed5365")
OTHER_TOPIC_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CHUNK_ID = "11111111-1111-1111-1111-111111111111"


class FakeSession:
    def __init__(self, topic):
        self.topic = topic
        self.lookup = None
        self.locked_for_update = False
        self.commit_calls = 0
        self.rollback_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, model, key, *, with_for_update=False):
        self.lookup = (model, key)
        self.locked_for_update = with_for_update
        return self.topic

    async def commit(self):
        self.commit_calls += 1

    async def rollback(self):
        self.rollback_calls += 1


def _topic():
    return SimpleNamespace(
        id=TOPIC_ID,
        content_summary=None,
    )


def _artifact():
    return {
        "content_summary": "Generated summary",
        "common_examples": [],
        "counterexamples": [],
        "typical_misconceptions": [],
        "essential_questions": [],
        "suitable_activities": [],
    }


def _card():
    return {
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


def _candidate(proposed_patch=None):
    if proposed_patch is None:
        proposed_patch = script.build_generated_topic_card_enrichment(
            _topic(),
            _card(),
            _artifact(),
            evidence_chunk_ids=[CHUNK_ID],
        )
    return script._build_candidate(
        topic_id=TOPIC_ID,
        topic_card_hash=script._topic_card_hash(_card()),
        artifact=_artifact(),
        proposed_patch=proposed_patch,
        evidence_chunk_ids=[CHUNK_ID],
    )


def _fail_session():
    pytest.fail("invalid candidate must not open a database session")


def _install_generation_fakes(monkeypatch, topic, session):
    card = _card()

    class FakeCatalog:
        async def get_topic_card(self, current_session, current_topic_id):
            return card

    class FakeRetrieval:
        async def retrieve(self, current_session, request):
            return {
                "query": request.query,
                "mode": request.mode,
                "strict_source": False,
                "warnings": [],
                "hits": [
                    {
                        "chunk_id": CHUNK_ID,
                        "source_id": "22222222-2222-2222-2222-222222222222",
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
            return _artifact()

    monkeypatch.setattr(script, "SessionLocal", lambda: session)
    monkeypatch.setattr(script, "CurriculumCatalogService", lambda: FakeCatalog())
    monkeypatch.setattr(script, "RetrievalService", lambda: FakeRetrieval())
    monkeypatch.setattr(script, "get_generation_provider", lambda: FakeProvider())


def test_apply_saved_candidate_commits_exact_patch_without_provider(
    monkeypatch,
    tmp_path,
):
    candidate = _candidate()
    script._save_candidate(candidate, tmp_path)
    topic = _topic()
    session = FakeSession(topic)
    applied_patches = []

    def apply_spy(current_topic, patch):
        applied_patches.append(patch)
        for field, value in patch.items():
            setattr(current_topic, field, value)

    class FakeCatalog:
        async def get_topic_card(self, current_session, current_topic_id):
            assert current_session is session
            assert current_topic_id == TOPIC_ID
            return _card()

    monkeypatch.setattr(script, "SessionLocal", lambda: session)
    monkeypatch.setattr(script, "apply_topic_card_enrichment", apply_spy)
    monkeypatch.setattr(script, "CurriculumCatalogService", lambda: FakeCatalog())
    monkeypatch.setattr(
        script,
        "get_generation_provider",
        lambda: pytest.fail("provider must not be called while applying"),
    )
    monkeypatch.setattr(
        script,
        "RetrievalService",
        lambda: pytest.fail("retrieval must not run while applying"),
    )
    monkeypatch.setattr(
        script,
        "TopicEnrichmentGenerationService",
        lambda *args: pytest.fail("generation must not run while applying"),
    )

    result = asyncio.run(
        script.apply_saved_topic_candidate(
            topic_id=TOPIC_ID,
            candidate_id=candidate["candidate_id"],
            candidate_dir=tmp_path,
        )
    )

    assert result == 0
    assert session.lookup == (Topic, TOPIC_ID)
    assert session.locked_for_update is True
    assert session.commit_calls == 1
    assert session.rollback_calls == 0
    assert applied_patches == [candidate["proposed_patch"]]
    assert topic.content_summary == "Generated summary"
    assert topic.verification_status == "pending_review"
    assert topic.provenance == candidate["proposed_patch"]["provenance"]


def test_apply_rejects_candidate_for_different_topic(monkeypatch, tmp_path):
    candidate = _candidate()
    script._save_candidate(candidate, tmp_path)
    monkeypatch.setattr(script, "SessionLocal", _fail_session)

    result = asyncio.run(
        script.apply_saved_topic_candidate(
            topic_id=OTHER_TOPIC_ID,
            candidate_id=candidate["candidate_id"],
            candidate_dir=tmp_path,
        )
    )

    assert result == 1


def test_apply_rejects_hash_mismatch_without_commit(monkeypatch, tmp_path):
    candidate = _candidate()
    path = script._save_candidate(candidate, tmp_path)
    candidate["evidence_chunk_ids"].append("33333333-3333-3333-3333-333333333333")
    path.write_text(json.dumps(candidate), encoding="utf-8")
    monkeypatch.setattr(script, "SessionLocal", _fail_session)

    result = asyncio.run(
        script.apply_saved_topic_candidate(
            topic_id=TOPIC_ID,
            candidate_id=candidate["candidate_id"],
            candidate_dir=tmp_path,
        )
    )

    assert result == 1


def test_apply_rejects_corrupt_candidate_without_commit(monkeypatch, tmp_path):
    candidate = _candidate()
    path = script._save_candidate(candidate, tmp_path)
    path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(script, "SessionLocal", _fail_session)

    result = asyncio.run(
        script.apply_saved_topic_candidate(
            topic_id=TOPIC_ID,
            candidate_id=candidate["candidate_id"],
            candidate_dir=tmp_path,
        )
    )

    assert result == 1


def test_apply_rejects_candidate_without_patch(monkeypatch, tmp_path):
    candidate = _candidate(proposed_patch={})
    script._save_candidate(candidate, tmp_path)
    monkeypatch.setattr(script, "SessionLocal", _fail_session)

    result = asyncio.run(
        script.apply_saved_topic_candidate(
            topic_id=TOPIC_ID,
            candidate_id=candidate["candidate_id"],
            candidate_dir=tmp_path,
        )
    )

    assert result == 1


def test_apply_rejects_metadata_only_candidate(monkeypatch, tmp_path):
    candidate = _candidate(proposed_patch={"verification_status": "verified"})
    script._save_candidate(candidate, tmp_path)
    monkeypatch.setattr(script, "SessionLocal", _fail_session)

    result = asyncio.run(
        script.apply_saved_topic_candidate(
            topic_id=TOPIC_ID,
            candidate_id=candidate["candidate_id"],
            candidate_dir=tmp_path,
        )
    )

    assert result == 1


def test_apply_rejects_stale_candidate_without_commit(monkeypatch, tmp_path):
    candidate = _candidate()
    script._save_candidate(candidate, tmp_path)
    topic = _topic()
    topic.content_summary = "Reviewed summary"
    topic.provenance = {
        "content_summary": {
            "origin": "reviewed",
            "status": "verified",
        }
    }
    original_topic = vars(topic).copy()
    session = FakeSession(topic)

    class FakeCatalog:
        async def get_topic_card(self, current_session, current_topic_id):
            return _card()

    monkeypatch.setattr(script, "SessionLocal", lambda: session)
    monkeypatch.setattr(script, "CurriculumCatalogService", lambda: FakeCatalog())

    result = asyncio.run(
        script.apply_saved_topic_candidate(
            topic_id=TOPIC_ID,
            candidate_id=candidate["candidate_id"],
            candidate_dir=tmp_path,
        )
    )

    assert result == 1
    assert session.commit_calls == 0
    assert session.rollback_calls == 1
    assert vars(topic) == original_topic


@pytest.mark.parametrize("changed_field", ["title", "learning_outcome"])
def test_apply_rejects_changed_curriculum_context_without_commit(
    monkeypatch,
    tmp_path,
    changed_field,
):
    candidate = _candidate()
    script._save_candidate(candidate, tmp_path)
    topic = _topic()
    original_topic = vars(topic).copy()
    session = FakeSession(topic)
    changed_card = _card()
    if changed_field == "title":
        changed_card["topic"]["title"] = "Revised topic"
    else:
        changed_card["learning_outcomes"][0]["text"] = "Revised outcome"

    class FakeCatalog:
        async def get_topic_card(self, current_session, current_topic_id):
            return changed_card

    monkeypatch.setattr(script, "SessionLocal", lambda: session)
    monkeypatch.setattr(script, "CurriculumCatalogService", lambda: FakeCatalog())

    result = asyncio.run(
        script.apply_saved_topic_candidate(
            topic_id=TOPIC_ID,
            candidate_id=candidate["candidate_id"],
            candidate_dir=tmp_path,
        )
    )

    assert result == 1
    assert session.locked_for_update is True
    assert session.commit_calls == 0
    assert session.rollback_calls == 1
    assert vars(topic) == original_topic


def test_generation_validation_failure_does_not_commit_or_save(
    monkeypatch,
    tmp_path,
):
    topic = _topic()
    original_topic = vars(topic).copy()
    session = FakeSession(topic)
    _install_generation_fakes(monkeypatch, topic, session)

    class InvalidGenerationService:
        def __init__(self, provider):
            pass

        async def generate(self, card, retrieval):
            raise TopicEnrichmentGenerationError("invalid generated artifact")

    monkeypatch.setattr(
        script,
        "TopicEnrichmentGenerationService",
        InvalidGenerationService,
    )

    result = asyncio.run(
        script.enrich_topic(
            topic_id=TOPIC_ID,
            apply=False,
            generate=True,
            candidate_dir=tmp_path,
        )
    )

    assert result == 1
    assert session.commit_calls == 0
    assert session.rollback_calls == 1
    assert vars(topic) == original_topic
    assert list(tmp_path.iterdir()) == []


def test_generation_without_patch_does_not_commit_or_save(
    monkeypatch,
    tmp_path,
):
    topic = _topic()
    original_topic = vars(topic).copy()
    session = FakeSession(topic)
    _install_generation_fakes(monkeypatch, topic, session)
    monkeypatch.setattr(
        script,
        "build_generated_topic_card_enrichment",
        lambda *args, **kwargs: {},
    )

    result = asyncio.run(
        script.enrich_topic(
            topic_id=TOPIC_ID,
            apply=False,
            generate=True,
            candidate_dir=tmp_path,
        )
    )

    assert result == 1
    assert session.commit_calls == 0
    assert session.rollback_calls == 1
    assert vars(topic) == original_topic
    assert list(tmp_path.iterdir()) == []


def test_generate_and_apply_are_rejected_before_provider_or_session(monkeypatch):
    monkeypatch.setattr(script, "SessionLocal", _fail_session)
    monkeypatch.setattr(
        script,
        "get_generation_provider",
        lambda: pytest.fail("provider must not be called"),
    )

    result = asyncio.run(
        script.enrich_topic(
            topic_id=TOPIC_ID,
            apply=True,
            generate=True,
        )
    )

    assert result == 1
