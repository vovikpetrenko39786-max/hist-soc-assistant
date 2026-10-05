# Controlled Web Fallback v1.3

## Назначение

Внешний интернет не заменяет библиотеку. Он используется как отдельный,
аудируемый слой знаний.

Основной порядок:

```text
Topic Card
→ Local Source Catalog / RAG
→ Controlled web fallback when needed
→ Generation context
→ Generator
→ Quality Gate
```

## Политики

### `library_only`

Внешний поиск запрещён.

### `library_first`

По умолчанию используется локальная библиотека. Web search запускается, если:

- локальных hits недостаточно;
- запрос явно требует свежей/текущей информации.

### `official_web_first`

Внешний официальный поиск выполняется обязательно и дополняет локальный RAG.

## OpenAI integration

Используется OpenAI Responses API:

```text
POST https://api.openai.com/v1/responses
```

с hosted tool:

```json
{"type": "web_search"}
```

Для официального режима передаётся:

```json
{
  "filters": {
    "allowed_domains": ["fipi.ru", "doc.fipi.ru"]
  }
}
```

В запрос включается:

```json
"include": ["web_search_call.action.sources"]
```

Поэтому backend сохраняет не только итоговый текст модели, но и список URL,
которые реально использовал web search.

## Официальные домены v1.3

Экзамены:

- `fipi.ru`
- `doc.fipi.ru`

Федеральные образовательные материалы:

- `edsoo.ru`
- `edu.gov.ru`
- `minobrnauki.gov.ru`

Право:

- `publication.pravo.gov.ru`
- `pravo.gov.ru`
- `kremlin.ru`
- `government.ru`

Статистика:

- `rosstat.gov.ru`

Domain policy можно расширять без изменения генератора.

## Двухступенчатый fallback

Если официальный поиск был выполнен, но не вернул ни одного usable source,
v1.3 может выполнить общий web search.

Это поведение управляется:

```env
WEB_ALLOW_GENERAL_AFTER_OFFICIAL=true
```

## API key

Ключ хранится только на backend:

```env
OPENAI_API_KEY=...
```

Он не попадает:

- в Telegram;
- в мобильный клиент;
- в браузер;
- в generated files;
- в git repository.

## Dry run

`dry_run=true` никогда не расходует web-search запрос.

Вместо этого возвращается:

```text
planned=true
allowed_domains=[...]
```

Это позволяет проверить маршрутизацию перед реальным API-вызовом.

## Аудит

Каждый внешний поиск сохраняется в:

`web_search_runs`

Записываются:

- query;
- policy;
- official/general scope;
- provider/model;
- allowed domains;
- response;
- source URLs;
- status;
- error.

## Telegram requirement

Если Telegram показывает пользователю факты, полученные через web search,
источники должны быть показаны как видимые кликабельные ссылки.

Telegram adapter не должен скрывать факт использования внешнего интернета.

## Что не делает v1.3

v1.3 не «заходит в чат ChatGPT».

Backend напрямую использует OpenAI API. Локальная база и пользовательские данные
остаются в нашем backend независимо от модели.
