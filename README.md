# History & Social Studies Teacher Assistant — MVP v0.1

Первый технический каркас цифрового ассистента учителя истории и обществознания.

## Что уже заложено

- FastAPI backend.
- PostgreSQL как основная БД.
- Готовность к pgvector/RAG.
- Сущности: учитель, класс, курс, поток класса, урок, прогресс, ДЗ, источник,
  chunk источника, созданный материал.
- Router: определяет тип запроса, предмет, класс и режим.
- Memory service: собирает контекст конкретного курса.
- Жизненный цикл урока: `planned -> completed / partially_completed`.
- Источник и chunk отделены от учебного процесса.
- Архитектура не привязана к Telegram или конкретному LLM.

## Быстрый запуск

1. Скопировать `.env.example` в `.env`.
2. Запустить PostgreSQL:

```bash
docker compose up -d
```

3. Создать виртуальное окружение и установить проект:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -e .
```

4. Запустить API:

```bash
uvicorn app.main:app --reload
```

5. Открыть:

- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Первый тест Router

POST `/api/v1/router/preview`

```json
{
  "text": "Завтра 10 класс. Обществознание. Сделай полноценный урок по социальным институтам."
}
```

Ожидаемая логика:

```json
{
  "task": "lesson",
  "subject": "social_studies",
  "grade": 10,
  "mode": "full"
}
```

## Следующий этап

1. Alembic migrations.
2. Импорт текущего паспорта преподавателя и классов.
3. Импорт списка учебников.
4. PDF ingestion: metadata -> text -> chunks -> embeddings.
5. Hybrid retrieval + rerank.
6. LLM provider interface.
7. SOP runtime registry.
8. Lesson generator.
9. Assessment generator.
10. Telegram UI после стабилизации ядра.


## Curriculum Catalog v0.1

Добавлен универсальный слой содержания: subjects, grade_levels, curricula, curriculum_units, topics, learning_outcomes, concepts, skills, topic_sources и exam links. Он не привязан к конкретному учителю.

Seed: `python -m scripts.seed_catalog_core`

API: `/api/v1/catalog/subjects`, `/curricula`, `/topics/search`, `/topics/{topic_id}`.

## Official Curriculum Dataset 2026/2027 — v0.3

Добавлен первый реальный глобальный dataset на основе действующих федеральных рабочих программ ЕДСОО.

- 5 официальных программ-источников;
- 12 курсов;
- 40 разделов;
- 111 тем/структурных узлов;
- детальная структура базового обществознания 9–11;
- официальный каркас истории 5–11 и углублённого обществознания 10–11;
- Topic → official program source binding;
- dependency-free validator.

Проверка:

```bash
python -m scripts.validate_curriculum_dataset
```

Импорт в PostgreSQL:

```bash
python -m scripts.import_official_curricula
```

Подробности: `docs/OFFICIAL_CURRICULUM_BASE_2026_2027.md`.

## Topic Cards v0.4

Глобальный curriculum dataset расширен до содержательного педагогического ядра.

Добавлено:

- детализированная нормализованная история 5–11;
- детализированное углублённое обществознание 10–11;
- learning outcomes;
- concepts;
- skills;
- lesson blueprints;
- misconceptions;
- essential questions;
- interdisciplinary links;
- broad OGE/EGE 2027 links;
- FIPI 2027 project source records.

Проверка:

```bash
python scripts/validate_curriculum_dataset.py
```

Подробнее: `docs/TOPIC_CARDS_V0_4.md`.


## Exam Mapping v0.5

Добавлен отдельный универсальный слой экзаменационных моделей 2027: статус проекта, ресурсы ФИПИ, подтверждённые изменения, кодификаторный baseline ЕГЭ обществознания и безопасные уровни достоверности mapping. См. `docs/EXAM_MAPPING_V0_5.md`.

Импорт:

```bash
python -m scripts.import_exam_mapping_2027
```

Проверка dataset:

```bash
python -m scripts.validate_exam_mapping
```


## Source Catalog v0.6

Добавлен универсальный слой учебников/источников: ФПУ-идентификаторы, библиографическая верификация, rollout/availability и resolver по предмету, классу, уровню и разделу.

Файлы: `data/source_catalog_seed_2026_2027.json`, `data/topic_source_candidates_v0_6.json`, `docs/SOURCE_CATALOG_V0_6.md`.

API: `GET /api/v1/sources`, `POST /api/v1/sources/resolve-preview`.


## PDF Ingestion v0.7

Source Catalog теперь поддерживает фактический импорт PDF:

- SHA-256 дедупликация;
- страничное извлечение текста;
- отдельные `source_pages`;
- PDF TOC -> `source_sections`;
- chunks с реальными page spans;
- `needs_ocr` для сканов;
- audit trail через `source_ingestion_runs`;
- embeddings пока `pending`, поэтому система не выставляет `rag_ready` преждевременно.

API:

```text
POST /api/v1/sources/{source_id}/ingest
GET  /api/v1/sources/{source_id}/ingestion-status
```

Проверка pipeline:

```bash
python scripts/validate_pdf_ingestion_pipeline.py
```

Подробности: `docs/PDF_INGESTION_V0_7.md`.


## RAG Retrieval Engine v0.8

Добавлены:

- embedding pipeline;
- PostgreSQL FTS + pgvector hybrid search;
- strict-source;
- exact phrase retrieval;
- metadata reranking;
- verified page references;
- safe quote flag.

API:

```text
POST /api/v1/retrieval/sources/{source_id}/embed
POST /api/v1/retrieval/search
GET  /api/v1/sources/{source_id}/pages/{page_number_pdf}
```

См. `docs/RAG_RETRIEVAL_V0_8.md`.


## Grounded Generation Engine v0.9

Pipeline:

```text
Curriculum Resolver
→ Topic Card
→ RAG
→ Grounding Context
→ Runtime SOP
→ Generation Provider
→ Quality Gate
→ Generation Run
```

API:

```text
POST /api/v1/generation/lesson
```

Поддерживается `dry_run=true`: он показывает весь контекст генерации до вызова модели.

По умолчанию используется локальный `template` provider для тестирования.
Production LLM подключается через абстракцию provider и не меняет бизнес-логику.

См. `docs/GROUNDED_GENERATION_V0_9.md`.


## Pedagogy Core v1.0

Единый endpoint `POST /api/v1/pedagogy/generate` создаёт lesson, assessment, worksheet, homework и idea_enhancement. Поддерживаются teacher/student/both, dry-run, RAG grounding и Quality Gate. См. `docs/PEDAGOGY_CORE_V1_0.md`.


## Production Output Layer v1.1

Экспорт педагогических артефактов в DOCX/PDF с отдельными teacher/student версиями.

API:

```text
GET  /api/v1/outputs/templates
POST /api/v1/outputs/render
GET  /api/v1/outputs/files/{export_id}
GET  /api/v1/outputs/runs/{run_id}
```

Шаблоны: `school_clean`, `compact_print`. См. `docs/PRODUCTION_OUTPUT_V1_1.md`.


## Natural Language Workflow v1.2

Один пользовательский вход:

```text
POST /api/v1/assistant
POST /api/v1/assistant/preview
```

Пример:

```text
10 класс, обществознание, социальные институты.
Сделай полноценный урок и рабочий лист в двух версиях, сразу в Word.
```

Workflow сам определяет предмет, класс, тему, типы материалов,
teacher/student versions и формат экспорта.

См. `docs/NATURAL_LANGUAGE_WORKFLOW_V1_2.md`.


## Controlled Web Fallback v1.3

Knowledge policies:

```text
library_only
library_first
official_web_first
```

OpenAI Responses API + hosted `web_search` is used for external fallback.

Diagnostics:

```text
POST /api/v1/web/search
GET  /api/v1/web/official-domains
```

Every external search is auditable through `web_search_runs`.

See `docs/CONTROLLED_WEB_FALLBACK_V1_3.md`.

Setup: `docs/OPENAI_WEB_SETUP_V1_3.md`.


## Telegram Pilot 1.0 / v1.4

Первый пользовательский интерфейс продукта:

```text
Telegram → /api/v1/assistant → Pedagogy Core → DOCX/PDF
```

Запуск:

```bash
python -m telegram_bot.main
```

Новые функции:
- `/start`, `/help`, `/status`, `/feedback`;
- кнопки основных педагогических сценариев;
- свободный natural-language input;
- отправка DOCX/PDF;
- сохранение отзывов реальных учителей;
- OpenAI Responses provider для всех основных артефактов;
- административная загрузка новых PDF-книг без обновления бота.

См. `docs/PILOT_1_0_LAUNCH_RU.md`.
