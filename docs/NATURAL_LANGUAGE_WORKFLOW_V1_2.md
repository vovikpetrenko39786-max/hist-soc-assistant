# Natural Language Workflow v1.2

## Цель

Один пользовательский запрос должен запускать весь внутренний pipeline.

Учитель пишет:

> 10 класс, обществознание, социальные институты.
> Сделай полноценный урок и рабочий лист в двух версиях, сразу в Word.

Backend сам определяет:

- предмет;
- класс;
- уровень;
- тему;
- режим;
- один или несколько типов материала;
- teacher/student versions;
- DOCX/PDF;
- параметры проверочной, если они названы.

## Единый endpoint

```text
POST /api/v1/assistant
```

Request:

```json
{
  "message": "10 класс, обществознание, социальные институты. Сделай полноценный урок и рабочий лист в двух версиях, сразу в Word.",
  "auto_render": true
}
```

## Preview

До запуска генерации можно посмотреть интерпретацию:

```text
POST /api/v1/assistant/preview
```

Это особенно важно для будущего Telegram UI.

## Pipeline

```text
Natural language
→ Intent parser
→ Workflow Plan
→ Pedagogy Core
→ Topic Card
→ RAG
→ Quality Gate
→ Output Layer
→ downloadable files
```

## Multi-artifact request

Один запрос может создать сразу:

- lesson;
- assessment;
- worksheet;
- homework.

Каждый материал получает собственный `generation_run`.

## Output

Если пользователь явно написал Word/DOCX или PDF,
workflow автоматически вызывает Production Output Layer.

Если формат не указан, возвращается сгенерированный workflow без обязательного
создания файлов.

## Knowledge policy

Workflow хранит отдельное решение:

### `library_first`

По умолчанию:

1. Curriculum/Topic Card;
2. Source Catalog;
3. локальный RAG;
4. при недостатке — разрешённый внешний fallback.

### `library_only`

Триггеры:

- «только библиотека»;
- «не ищи в интернете»;
- «без интернета».

### `official_web_first`

Для запросов вроде:

- «актуальные данные»;
- «проверь в интернете»;
- «последние данные».

В v1.2 это уже часть workflow plan.
Сам внешний web-search provider подключается следующим интеграционным слоем.

## Telegram

Telegram-бот в будущем не должен повторять эту бизнес-логику.

Он отправляет текст пользователя в:

```text
POST /api/v1/assistant
```

и получает:

- понятный summary;
- результаты;
- download paths для DOCX/PDF.

Таким образом Telegram является интерфейсом, а не «мозгом» продукта.
