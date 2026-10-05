# OpenAI Web Search Setup — v1.3

Дата проверки документации: 2026-10-05.

## Что подключено

Backend использует OpenAI Responses API и hosted tool `web_search`.

API key хранится только на сервере в переменной окружения `OPENAI_API_KEY`.
Никогда не вставляйте реальный ключ в исходный код, Telegram-бот или публичный репозиторий.

## 1. Создать API key

Создайте отдельный project/API key в OpenAI Platform для Teacher Assistant.
Рекомендуется отдельный ключ именно для этого backend, чтобы usage было проще отслеживать.

Ключ нельзя отправлять в чат или хранить в репозитории.

## 2. Настроить `.env`

Скопируйте `.env.example` в `.env` и заполните:

```env
OPENAI_API_KEY=...
OPENAI_RESPONSES_BASE_URL=https://api.openai.com/v1
WEB_SEARCH_PROVIDER=openai
WEB_SEARCH_MODEL=gpt-5.5
WEB_SEARCH_CONTEXT_SIZE=low
WEB_SEARCH_TIMEOUT_SECONDS=90
WEB_FALLBACK_MIN_LOCAL_HITS=2
WEB_ALLOW_GENERAL_AFTER_OFFICIAL=true
WEB_MAX_SOURCES=12
```

`WEB_SEARCH_MODEL` является конфигурируемым и может быть заменён без изменения бизнес-логики.

## 3. Проверить domain routing без расхода API

```text
GET /api/v1/web/official-domains?query=изменения%20ЕГЭ-2027%20история&subject=HISTORY
```

Ожидаемый результат должен включать `fipi.ru` и `doc.fipi.ru`.

## 4. Проверить dry run основного workflow

```json
POST /api/v1/assistant
{
  "message": "11 класс, история. Добавь актуальные изменения ЕГЭ-2027 и проверь в интернете.",
  "dry_run": true
}
```

Dry run не вызывает внешний web search и не расходует API usage.

## 5. Выполнить реальный diagnostic web search

```json
POST /api/v1/web/search
{
  "query": "Изменения ЕГЭ-2027 по истории",
  "subject": "HISTORY",
  "policy": "official_web_first",
  "scope": "official",
  "force_search": true
}
```

Backend должен вернуть:

- `answer`;
- `sources`;
- `citations`;
- `allowed_domains`;
- `search_run_id`.

## 6. Проверить audit log

Каждый реальный поиск сохраняется в `web_search_runs`.

Если позже возникнет спорный ответ, можно восстановить:

- какой запрос отправлялся;
- какая модель использовалась;
- какие домены были разрешены;
- какие URL вернул поиск;
- какой текст пришёл от API.

## 7. Telegram

Telegram не получает `OPENAI_API_KEY`.

Telegram отправляет пользовательский текст нашему backend, а backend уже вызывает
OpenAI API при необходимости.

Таким образом утечка Telegram bot token не раскрывает OpenAI API key, и наоборот.

## Полезные официальные страницы

- OpenAI web search guide: https://developers.openai.com/api/docs/guides/tools-web-search
- API key safety: https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety
