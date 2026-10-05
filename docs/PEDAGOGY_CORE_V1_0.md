# Pedagogy Core v1.0

Первая версия универсального педагогического ядра, которое создаёт основные артефакты из одного pipeline:

`Curriculum Resolver → Topic Card → RAG → Runtime SOP → Artifact Generator → Teacher/Student split → Quality Gate → Audit`.

## Единый endpoint

`POST /api/v1/pedagogy/generate`

Поддерживаются `lesson`, `assessment`, `worksheet`, `homework`, `idea_enhancement`.

### Урок
```json
{"artifact_type":"lesson","subject":"SOCIAL_STUDIES","grade":10,"level":"basic","topic":"Социальные институты","duration_minutes":45,"audience":"teacher"}
```

### Проверочная: версии ученик + учитель
```json
{"artifact_type":"assessment","subject":"HISTORY","grade":6,"topic":"Древняя Русь","audience":"both","assessment":{"task_count":6,"max_points":20,"difficulty":"mixed","assessment_type":"check"}}
```

### Рабочий лист
```json
{"artifact_type":"worksheet","subject":"SOCIAL_STUDIES","grade":9,"topic":"Традиционные ценности","audience":"both"}
```

### Домашнее задание
```json
{"artifact_type":"homework","subject":"HISTORY","grade":5,"topic":"Древний Египет","audience":"student","homework":{"duration_minutes":15,"purpose":"consolidation"}}
```

### IDEA Enhancer
```json
{"artifact_type":"idea_enhancement","request_text":"Хочу сделать урок как историческое расследование с уликами.","subject":"HISTORY","grade":7,"audience":"teacher"}
```

IDEA Enhancer сохраняет ядро идеи и выдаёт `minimal / optimal / bold`, риски и рекомендуемый вариант.

## Teacher / Student split

Для assessment и worksheet student version автоматически очищается от ответов и критериев. Для homework убирается teacher-only note. Это дополнительно проверяет Quality Gate.

## Quality Gate

Проверяет grounding источников и страниц для всех артефактов, а также специфические инварианты: баллы и ключи у assessment, отсутствие ответов у student worksheet, время и критерии homework, сохранение ядра идеи у IDEA Enhancer.

## Совместимость

Старый `/api/v1/generation/lesson` остаётся рабочим. Новый `/api/v1/pedagogy/generate` — основной универсальный интерфейс v1.0.
