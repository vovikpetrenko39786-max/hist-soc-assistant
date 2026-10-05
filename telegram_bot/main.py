from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, Message

from app.core.config import get_settings
from telegram_bot.api_client import BackendClientError, TeacherAssistantApi
from telegram_bot.keyboards import main_keyboard
from telegram_bot.modes import BUTTON_PREFIXES
from telegram_bot.texts import BETA_NOTICE, HELP_TEXT, START_TEXT

settings = get_settings()
router = Router()
api = TeacherAssistantApi(
    settings.telegram_backend_base_url,
    settings.telegram_request_timeout_seconds,
)


class BotState(StatesGroup):
    waiting_request = State()
    waiting_feedback = State()


def user_context(message: Message) -> dict:
    user = message.from_user
    return {
        "channel": "telegram",
        "telegram_user_id": str(user.id) if user else None,
        "username": user.username if user else None,
        "display_name": user.full_name if user else None,
        "chat_id": str(message.chat.id),
    }


async def send_workflow_result(message: Message, result: dict, state: FSMContext):
    await state.update_data(last_request=result.get("plan", {}).get("original_message"))
    summary = result.get("summary") or "Материал обработан."
    warnings = result.get("warnings") or []

    lines = [f"✅ {summary}"]
    if warnings:
        lines.append("\n⚠️ " + "\n⚠️ ".join(str(x) for x in warnings[:3]))
    if settings.telegram_beta_notice:
        lines.append("\n" + BETA_NOTICE)

    await message.answer("\n".join(lines), reply_markup=main_keyboard())

    for item in result.get("results", []):
        for file in item.get("files", []):
            path = None
            try:
                path = await api.download(file["download_path"], file["file_name"])
                label = "👩‍🏫 Для учителя" if file.get("audience") == "teacher" else "👨‍🎓 Для ученика"
                await message.answer_document(
                    FSInputFile(path, filename=file["file_name"]),
                    caption=f"{label} · {item.get('artifact_type')}",
                )
            except Exception as exc:
                await message.answer(
                    f"⚠️ Материал создан, но файл «{file.get('file_name')}» не удалось отправить: {exc}"
                )
            finally:
                if path:
                    Path(path).unlink(missing_ok=True)


async def process_request(message: Message, state: FSMContext, text: str):
    request_id = str(uuid.uuid4())[:8]
    status_message = await message.answer(
        f"⏳ Готовлю материал…\nID запроса: <code>{request_id}</code>"
    )
    try:
        result = await api.assistant(text, user_context(message))
        await status_message.edit_text(
            f"✅ Обработка завершена.\nID запроса: <code>{request_id}</code>"
        )
        await state.update_data(last_run_id=_find_run_id(result), last_request=text)
        await send_workflow_result(message, result, state)
    except Exception as exc:
        logging.exception("Request failed id=%s user=%s", request_id, message.from_user.id if message.from_user else None)
        await status_message.edit_text(
            "❌ Не получилось обработать запрос.\n"
            f"ID ошибки: <code>{request_id}</code>\n\n"
            "Нажмите «🐞 Ошибка / отзыв» и, если можете, опишите, что вы ожидали получить."
        )
        await state.update_data(last_request=text, last_error_id=request_id, last_error=str(exc)[:1500])


def _find_run_id(result: dict) -> str | None:
    for item in result.get("results", []):
        if item.get("run_id"):
            return item["run_id"]
    return None


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(START_TEXT, reply_markup=main_keyboard())


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, reply_markup=main_keyboard())


@router.message(Command("whoami"))
async def cmd_whoami(message: Message):
    await message.answer(
        f"Telegram user ID: <code>{message.from_user.id if message.from_user else 'unknown'}</code>"
    )


@router.message(Command("status"))
@router.message(F.text == "✅ Статус")
async def cmd_status(message: Message):
    try:
        data = await api.health()
        await message.answer(
            "✅ Система доступна\n"
            f"Релиз: <b>{data.get('release')}</b>\n"
            f"OpenAI: {'✅' if data.get('openai_configured') else '⚠️ не подключён'}\n"
            f"Генератор: <code>{data.get('generation_provider')}</code>\n"
            f"Модель: <code>{data.get('generation_model')}</code>",
            reply_markup=main_keyboard(),
        )
    except Exception as exc:
        await message.answer(f"❌ Backend недоступен: {exc}", reply_markup=main_keyboard())


@router.message(F.text == "🐞 Ошибка / отзыв")
@router.message(Command("feedback"))
async def begin_feedback(message: Message, state: FSMContext):
    await state.set_state(BotState.waiting_feedback)
    await message.answer(
        "Напишите свободным текстом, что произошло или что хотелось бы улучшить.\n\n"
        "Можно писать очень просто: «в проверочной слишком лёгкие задания», "
        "«не нашёл тему», «Word хороший, но нужен другой шрифт» и т. п."
    )


@router.message(BotState.waiting_feedback)
async def save_feedback(message: Message, state: FSMContext):
    data = await state.get_data()
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пришлите отзыв текстом.")
        return
    category = "bug" if data.get("last_error_id") else "feedback"
    payload = {
        "category": category,
        "channel": "telegram",
        "user_external_id": str(message.from_user.id) if message.from_user else None,
        "username": message.from_user.username if message.from_user else None,
        "display_name": message.from_user.full_name if message.from_user else None,
        "text": text,
        "last_request": data.get("last_request"),
        "generation_run_id": data.get("last_run_id"),
        "metadata": {
            "last_error_id": data.get("last_error_id"),
            "last_error": data.get("last_error"),
        },
    }
    try:
        response = await api.feedback(payload)
        await message.answer(
            f"💬 Спасибо! Отзыв сохранён.\nID: <code>{response.get('id')}</code>",
            reply_markup=main_keyboard(),
        )
    except Exception as exc:
        await message.answer(
            f"⚠️ Не удалось сохранить отзыв в базе: {exc}\n"
            "Скопируйте сообщение и передайте владельцу бота.",
            reply_markup=main_keyboard(),
        )
    await state.clear()


@router.message(F.text.in_(set(BUTTON_PREFIXES.keys())))
async def choose_mode(message: Message, state: FSMContext):
    prefix = BUTTON_PREFIXES[message.text]
    await state.set_state(BotState.waiting_request)
    await state.update_data(request_prefix=prefix)
    await message.answer(
        "Теперь напишите запрос одним сообщением.\n\n"
        "Лучше указать: класс, предмет, тему и пожелания.\n"
        "Например: «10 класс, обществознание, социальные институты, 45 минут, Word»."
    )


@router.message(BotState.waiting_request)
async def mode_request(message: Message, state: FSMContext):
    data = await state.get_data()
    prefix = data.get("request_prefix", "")
    await state.set_state(None)
    await process_request(message, state, prefix + (message.text or ""))


@router.message(F.text)
async def free_text(message: Message, state: FSMContext):
    if message.text.startswith("/"):
        return
    await process_request(message, state, message.text)


async def main():
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not configured. Put it in .env; do not hard-code it."
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # Polling is intentionally used for Pilot 1.0: no public webhook URL required.
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
        tasks_concurrency_limit=20,
    )


if __name__ == "__main__":
    asyncio.run(main())
