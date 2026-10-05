from app.schemas.workflow import NaturalWorkflowRequest
from app.services.natural_language_workflow import NaturalLanguageParser


def test_current_exam_request_routes_to_official_web_first():
    plan = NaturalLanguageParser().parse(
        NaturalWorkflowRequest(
            message=(
                "11 класс, история, международные отношения. "
                "Добавь актуальные изменения ЕГЭ-2027 и проверь в интернете."
            )
        )
    )
    assert plan.knowledge_policy == "official_web_first"
    assert plan.web_fallback_allowed is True


def test_no_internet_phrase_routes_to_library_only():
    plan = NaturalLanguageParser().parse(
        NaturalWorkflowRequest(
            message=(
                "9 класс, обществознание, традиционные ценности. "
                "Сделай урок только по библиотеке, без интернета."
            )
        )
    )
    assert plan.knowledge_policy == "library_only"
    assert plan.web_fallback_allowed is False
