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
