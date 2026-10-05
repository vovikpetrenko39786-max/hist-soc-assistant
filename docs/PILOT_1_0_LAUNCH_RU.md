# Пилот «Ассистент учителя» 1.0 — запуск для коллег

## Что нужно от владельца проекта

Для тестовой версии достаточно четырёх вещей:

1. Telegram-бот от `@BotFather`.
2. `TELEGRAM_BOT_TOKEN` — хранится только в `.env`, не отправляется в чаты.
3. `OPENAI_API_KEY` с API-биллингом.
4. Компьютер, который будет включён во время пилота, **или** VPS/сервер.

Для пилота на несколько коллег публичный домен не нужен: используется Telegram long polling.

---

## Шаг 1. Создать бота

В Telegram открыть `@BotFather`.

Отправить:

```text
/newbot
```

Задать:
- отображаемое имя;
- username бота.

BotFather выдаст token.

**Token никому не пересылать.**

Скопировать его в `.env`:

```env
TELEGRAM_BOT_TOKEN=...
```

Полезно также через BotFather заполнить:
- `/setdescription`
- `/setabouttext`
- `/setuserpic`

---

## Шаг 2. OpenAI API

В `.env`:

```env
OPENAI_API_KEY=...
GENERATION_PROVIDER=openai_responses
OPENAI_GENERATION_MODEL=gpt-5.6-terra
WEB_SEARCH_MODEL=gpt-5.6-luna
```

Для production semantic retrieval рекомендуется:

```env
EMBEDDING_PROVIDER=http
EMBEDDING_HTTP_BASE_URL=https://api.openai.com/v1
EMBEDDING_HTTP_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
```

`EMBEDDING_HTTP_API_KEY` можно оставить пустым: backend использует `OPENAI_API_KEY`.

---

## Шаг 3. Админ-ключ

Придумать длинную случайную строку:

```env
ADMIN_API_KEY=...
```

Она нужна для просмотра отзывов и административной загрузки книг.

---

## Шаг 4. Установка

Нужны:
- Python 3.12+;
- Docker Desktop;
- LibreOffice — только если нужен PDF локально.

В корне проекта:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

После этого заполнить `.env`.

---

## Шаг 5. Запустить PostgreSQL

```powershell
docker compose up -d postgres
```

---

## Шаг 6. Первый запуск backend

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Открыть в браузере:

```text
http://127.0.0.1:8000/health
```

Затем:

```text
http://127.0.0.1:8000/api/v1/pilot/health
```

---

## Шаг 7. Инициализировать базу

В отдельном PowerShell:

```powershell
python scripts/pilot_init.py
```

Это загружает универсальные программы, экзаменационный mapping и Source Catalog.

---

## Шаг 8. Запустить Telegram

```powershell
python -m telegram_bot.main
```

Открыть бота → `/start`.

Проверить `/status`.

Если:
- backend ✅;
- OpenAI ✅;
- модель отображается;

можно тестировать.

---

## Быстрый запуск в следующие дни

Когда всё уже установлено:

```powershell
.\scripts\start_pilot_windows.ps1
```

Пока компьютер включён и окна backend/bot работают, коллеги могут пользоваться ботом из любого места через Telegram.

---

## Что дать коллегам

Не объяснять им архитектуру.

Сказать:

> Это тестовый ассистент учителя. Пользуйтесь как хотите: нажимайте кнопки, пишите обычным языком, пробуйте странные запросы. Важно не только то, что работает, но и всё, что раздражает, непонятно, неверно или неудобно. Для этого есть кнопка «Ошибка / отзыв».

---

## Что обязательно протестировать перед демонстрацией

1. `/start`
2. `/status`
3. Свободный запрос на урок.
4. Проверочная в двух версиях.
5. Рабочий лист.
6. Word-файл.
7. PDF, если установлен LibreOffice.
8. Актуальный вопрос ЕГЭ/ОГЭ с web fallback.
9. Кнопка «Ошибка / отзыв».
10. Перезапуск бота.

---

## Если бот перестал отвечать

Сначала:

```text
/status
```

Если статус не открывается:
- проверить окно backend;
- проверить окно Telegram bot;
- проверить интернет;
- проверить, что `.env` не изменён;
- сохранить текст ошибки.

Не менять код наугад.

---

## Пилот ≠ финальный продукт

Для пилота допустимы:
- неполная библиотека;
- отдельные неидеальные темы;
- отсутствие персонализации классов;
- ошибки интерфейса.

Цель пилота — собрать **живые сценарии реальных учителей**.
