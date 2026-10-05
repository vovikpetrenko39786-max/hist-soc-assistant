from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📚 Создать урок"),
                KeyboardButton(text="📝 Проверочная"),
            ],
            [
                KeyboardButton(text="📄 Рабочий лист"),
                KeyboardButton(text="🏠 Домашнее задание"),
            ],
            [
                KeyboardButton(text="🎓 ОГЭ / ЕГЭ"),
                KeyboardButton(text="🔎 Найти в библиотеке"),
            ],
            [
                KeyboardButton(text="💡 Улучшить идею"),
                KeyboardButton(text="🐞 Ошибка / отзыв"),
            ],
            [
                KeyboardButton(text="ℹ️ Помощь"),
                KeyboardButton(text="✅ Статус"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напишите запрос учителю-ассистенту…",
    )
