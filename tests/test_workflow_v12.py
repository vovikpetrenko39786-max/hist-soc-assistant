from app.schemas.workflow import NaturalWorkflowRequest
from app.services.natural_language_workflow import NaturalLanguageParser


def parser(message, **kwargs):
    return NaturalLanguageParser().parse(
        NaturalWorkflowRequest(message=message, **kwargs)
    )


def test_multi_artifact_teacher_shorthand():
    plan = parser(
        "10 класс, обществознание, социальные институты. "
        "Сделай полноценный урок и рабочий лист в двух версиях, сразу в Word."
    )
    assert plan.grade == 10
    assert plan.subject == "SOCIAL_STUDIES"
    assert plan.topic.lower() == "социальные институты"
    assert plan.mode == "full"
    assert [x.artifact_type for x in plan.artifacts] == ["lesson", "worksheet"]
    assert plan.artifacts[1].audience == "both"
    assert plan.formats == ["docx"]


def test_assessment_options_and_pdf():
    plan = parser(
        "6 класс, история, Древний Египет. "
        "Подготовь проверочную на 8 заданий, максимум 20 баллов, "
        "учитель и ученик, PDF."
    )
    assert plan.subject == "HISTORY"
    assert plan.grade == 6
    assert plan.topic == "Древний Египет"
    assert plan.assessment_task_count == 8
    assert plan.assessment_max_points == 20
    assert plan.artifacts[0].artifact_type == "assessment"
    assert plan.artifacts[0].audience == "both"
    assert plan.formats == ["pdf"]


def test_library_only_policy():
    plan = parser(
        "9 класс, обществознание, традиционные ценности. "
        "Сделай урок. Только библиотека, без интернета."
    )
    assert plan.knowledge_policy == "library_only"
    assert plan.web_fallback_allowed is False


def test_current_info_requests_official_web_first():
    plan = parser(
        "11 класс, история, международные отношения. "
        "Добавь актуальные данные и проверь в интернете."
    )
    assert plan.knowledge_policy == "official_web_first"
    assert plan.web_fallback_allowed is True


def test_word_and_pdf_both_detected():
    plan = parser(
        "5 класс, история, Древний Египет. Сделай рабочий лист в Word и PDF."
    )
    assert plan.formats == ["docx", "pdf"]


def test_idea_enhancement_does_not_require_topic():
    plan = parser(
        "Хочу сделать урок истории как историческое расследование с уликами. "
        "Улучши идею."
    )
    assert "idea_enhancement" in [x.artifact_type for x in plan.artifacts]
