from app.schemas.pedagogy import PedagogyGenerationRequest


def test_informational_request_does_not_require_topic():
    request = PedagogyGenerationRequest(
        artifact_type="informational",
        request_text="Что изменилось в ЕГЭ-2027 по истории?",
        subject="HISTORY",
        grade=11,
        level="exam",
        knowledge_policy="library_first",
    )

    assert request.artifact_type == "informational"
    assert request.topic is None
    assert request.topic_id is None
    assert request.knowledge_policy == "library_first"
