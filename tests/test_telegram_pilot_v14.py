from app.schemas.workflow import NaturalWorkflowRequest
from app.services.natural_language_workflow import NaturalLanguageParser
from telegram_bot.keyboards import main_keyboard
from telegram_bot.modes import BUTTON_PREFIXES
from telegram_bot.texts import START_TEXT


def test_start_text_mentions_pilot_and_feedback():
    assert "тестовая версия 1.0" in START_TEXT
    assert "Ошибка / отзыв" in START_TEXT


def test_core_buttons_exist():
    expected = {
        "📚 Создать урок",
        "📝 Проверочная",
        "📄 Рабочий лист",
        "🏠 Домашнее задание",
        "🎓 ОГЭ / ЕГЭ",
        "🔎 Найти в библиотеке",
        "💡 Улучшить идею",
    }
    assert expected.issubset(set(BUTTON_PREFIXES))


def test_assessment_button_forces_two_versions():
    assert "двух версиях" in BUTTON_PREFIXES["📝 Проверочная"]


def test_exam_button_requests_official_fipi():
    assert "ФИПИ" in BUTTON_PREFIXES["🎓 ОГЭ / ЕГЭ"]


def test_course_picker_is_visible_on_main_keyboard():
    labels = {
        button.text
        for row in main_keyboard().keyboard
        for button in row
    }
    assert "🧭 Мои курсы" in labels


def test_every_generation_button_routes_to_expected_artifact():
    expected = {
        "📚 Создать урок": "lesson",
        "📝 Проверочная": "assessment",
        "📄 Рабочий лист": "worksheet",
        "🏠 Домашнее задание": "homework",
        "🎓 ОГЭ / ЕГЭ": "informational",
        "🔎 Найти в библиотеке": "informational",
        "💡 Улучшить идею": "idea_enhancement",
    }
    suffix = "10 класс, обществознание, тема: Социальные институты. Word"
    parser = NaturalLanguageParser()
    for button, artifact_type in expected.items():
        plan = parser.parse(
            NaturalWorkflowRequest(message=BUTTON_PREFIXES[button] + suffix)
        )
        assert artifact_type in {item.artifact_type for item in plan.artifacts}, button


def test_lesson_button_requests_full_professional_mode():
    plan = NaturalLanguageParser().parse(
        NaturalWorkflowRequest(
            message=BUTTON_PREFIXES["📚 Создать урок"]
            + "10 класс, обществознание, тема: Социальные институты. Word"
        )
    )
    assert plan.mode == "full"
    assert plan.artifacts[0].artifact_type == "lesson"
