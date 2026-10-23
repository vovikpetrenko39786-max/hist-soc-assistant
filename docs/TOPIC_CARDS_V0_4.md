# Topic Cards v0.4 — универсальное педагогическое ядро

## Что изменилось

Dataset 2026/27 больше не является только перечнем тем. Каждый тематический узел теперь может содержать:

- предметные и метапредметные результаты;
- ключевые понятия;
- проверяемые навыки;
- методический blueprint урока;
- типичные заблуждения;
- сильный проблемный вопрос;
- рекомендуемые виды деятельности;
- рефлексию;
- межпредметные связи;
- связь с ОГЭ/ЕГЭ;
- нормативный источник.

## Важно о происхождении данных

Слой делится на две части.

### Official curriculum layer

Из федеральных рабочих программ берутся:

- структура курса;
- содержательные разделы;
- рекомендуемый объём часов;
- планируемые результаты как нормативная основа;
- тематическое планирование.

### Methodical normalization layer

Ассистент нормализует официальное содержание в удобную для генерации уроков форму:

- короткие тематические узлы;
- навыки;
- вопросы урока;
- типичные ошибки;
- lesson blueprint;
- форматы деятельности;
- варианты рефлексии.

Этот слой не является цитатой ФРП и хранится с соответствующим provenance.

## История 5–11

Статус `skeleton` снят.

Для 5–11 классов создана подробная нормализованная карта тем. Названия части узлов являются рабочей нормализацией содержания ФРП, а не заявляются как дословные заголовки официального документа.

Это позволяет Curriculum Resolver работать с запросами вида:

- `6 класс → Крестовые походы`;
- `8 класс → Пётр I`;
- `9 класс → Великие реформы`;
- `10 класс → Гражданская война`;
- `11 класс → Холодная война`.

## Обществознание

### 9 класс, базовый

Сохраняется детализированный курс на 34 часа.

### 10 класс, базовый

Сохраняется детализированный курс на 68 часов.

### 11 класс, базовый

Сохраняется детализированный курс на 34 часа.

### 10–11 классы, углублённый

Статус `skeleton` снят. Тематические разделы развернуты по федеральному тематическому планированию.

Углублённый уровень рассчитан на 136 часов в 10 классе и 136 часов в 11 классе.

## Экзаменационный слой 2027

В dataset добавлены официальные источники ФИПИ для проектов КИМ 2027.

На этом этапе связь имеет уровень:

`general_topic`

То есть система знает, что тема относится к предметному полю ОГЭ/ЕГЭ, но **не приписывает ей автоматически конкретный номер задания или позицию кодификатора**.

Следующий отдельный этап:

`Topic -> codifier item -> task model -> criteria -> navigator/open bank`

## Topic Card pipeline

```text
Subject + Grade + Level + Topic
        ↓
Curriculum Resolver
        ↓
Topic Card
        ↓
Official Source Resolver
        ↓
RAG
        ↓
Runtime SOP
        ↓
Lesson / Assessment / Worksheet Generator
```

### Pilot enrichment/backfill

The enrichment command operates only on the existing `SOCIAL_STUDIES`, grade 9,
`basic`, `Как устроено общество` Topic Card. It uses its existing learning
outcomes, concepts, lesson blueprint, and source links; it does not import the
dataset or modify catalog relationships. The default is a read-only dry run:

```bash
python -m scripts.enrich_topic_card --topic-id <TOPIC_UUID>
```

To persist the enrichment in the database configured for the process, pass
`--apply` explicitly:

```bash
python -m scripts.enrich_topic_card --topic-id <TOPIC_UUID> --apply
```

The generated summary and candidate pedagogical examples/questions are marked
`generated_candidate` or `methodical_mapping` and remain `pending_review`.
Existing generic reflection patterns and lesson blueprints are retained and
identified in provenance as system fallbacks, not topic-specific enrichment.
Reviewed fields are not overwritten, and verification is never upgraded to
`verified`.

### Generated enrichment candidates

Generated enrichment uses a two-phase workflow. Generation is always read-only
for the Topic and saves the exact artifact, proposed patch, evidence chunk IDs,
Topic ID, Topic Card context hash, and deterministic SHA-256 candidate ID to
the ignored local `outputs/topic-enrichment-candidates/` store:

```bash
python -m scripts.enrich_topic_card --topic-id <TOPIC_UUID> --generate
```

After reviewing the saved JSON, apply that exact candidate by the ID printed by
the generation command:

```bash
python -m scripts.enrich_topic_card \
  --topic-id <TOPIC_UUID> \
  --apply-candidate <CANDIDATE_ID>
```

Applying a candidate validates its schema, Topic ID, allowed patch fields, and
content hash, then confirms that the Topic Card context is unchanged and still
produces the same patch from the saved artifact and evidence. The Topic row is
locked during this check and commit. Applying does not call the generation
provider or generate new content. `--generate --apply` is rejected so generation
and persistence cannot happen in one step.

## Статистика v0.4

Актуальные значения проверяются скриптом:

```bash
python scripts/validate_curriculum_dataset.py
```

На момент сборки v0.4:

- 7 source records;
- 12 curricula;
- 42 curriculum units;
- 307 topic nodes;
- 1 535 topic outcome links;
- 1 769 topic skill links;
- 226 broad exam links;
- 244 interdisciplinary links.

## Ключевое ограничение

`reviewed` не означает `verified verbatim`.

Для нормализованных тем истории и методических полей Topic Card статус означает, что структура согласована с официальной программой, но формулировки могут быть педагогически нормализованы.

Точная цитата, страница ФРП или дословная формулировка всегда требуют обращения к первоисточнику.
