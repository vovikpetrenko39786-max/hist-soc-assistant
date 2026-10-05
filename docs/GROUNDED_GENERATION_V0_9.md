# Grounded Generation Engine v0.9

## Цель

Соединить универсальный Curriculum Catalog и RAG с реальным генератором урока:

`request`
→ `Curriculum Resolver`
→ `Topic Card`
→ `RAG`
→ `Grounding Context`
→ `Runtime SOP`
→ `Generation Provider`
→ `Quality Gate`
→ `Generation Run`

## Новый endpoint

```text
POST /api/v1/generation/lesson
```

Минимальный запрос:

```json
{
  "subject": "SOCIAL_STUDIES",
  "grade": 10,
  "level": "basic",
  "topic": "Социальные институты",
  "duration_minutes": 45
}
```

## Dry Run

Перед обращением к LLM можно проверить весь контекст:

```json
{
  "subject": "SOCIAL_STUDIES",
  "grade": 10,
  "level": "basic",
  "topic": "Социальные институты",
  "dry_run": true
}
```

Ответ покажет:

- разрешённую Topic Card;
- найденные RAG chunks;
- source manifest;
- runtime SOP;
- grounding contract.

Это главный режим отладки.

## Generation providers

### template

Детерминированный локальный generator для интеграционных тестов.

Он создаёт полноценную структуру урока без внешней модели и позволяет проверить
весь orchestration pipeline.

### http

Generic chat-completions-style provider.

Он получает только уже собранный контекст и обязан вернуть JSON по схеме
`LessonArtifact`.

## Grounding contract

Модель не выбирает страницы самостоятельно.

В context передаются конкретные retrieved chunks:

```text
chunk_id
source_id
title
section
page_pdf
page_print
snippet
```

`source_references` итогового урока являются только ссылками на эти entries.

Quality Gate проверяет это повторно после генерации.

## Quality Gate

Автоматически проверяются:

- точная сумма времени;
- наличие измеримых результатов;
- реальная деятельность ученика;
- evidence of learning;
- формирующая проверка;
- рефлексия;
- соответствие source references retrieval manifest;
- соответствие страниц retrieval manifest;
- покрытие обязательных понятий.

Генерация с критическими ошибками получает:

```text
quality_failed
```

и не маскируется под готовый качественный материал.

## Audit trail

Каждая генерация может сохраняться в `generation_runs`.

Сохраняются:

- запрос;
- resolved topic;
- provider/model;
- prompt hash;
- generation context;
- source manifest;
- output JSON;
- Quality Gate report.

Это позволит воспроизводить ошибки и проводить benchmark.

## Персонализация

v0.9 по-прежнему не требует карточки конкретного учителя.

Базовый запрос:

`предмет + класс + тема`

уже достаточен.

В дальнейшем Teacher/Class Context просто добавляется в generation context
между Topic Card и Runtime SOP.
