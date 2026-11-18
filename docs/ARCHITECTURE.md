# Целевая архитектура Hist-Soc Assistant

**Статус:** предлагаемая архитектура до закрытого пилота  
**Принцип:** эволюция существующего приложения без переписывания с нуля  
**Исходные ограничения:** выводы [TECHNICAL_AUDIT.md](TECHNICAL_AUDIT.md), требования [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)

## 1. Решение в одном абзаце

До и во время пилота Hist-Soc Assistant следует строить как **модульный монолит**: PWA-клиент, FastAPI API, отдельный worker, PostgreSQL + pgvector, Redis или PostgreSQL job queue и S3-compatible object storage. Identity задаёт доверенный server-side principal; tenant isolation обеспечивается одновременно policy layer, tenant-aware foreign keys и PostgreSQL RLS. Учебные источники и результаты неизменяемо версионируются. Генерация является наблюдаемым многостадийным workflow, а не одним LLM-вызовом. Telegram использует тот же API как связанный канал, но не определяет личность пользователя самостоятельно.

Микросервисы на 3–4 пользователей добавят эксплуатационный риск и не нужны. Границы модулей должны позволить выделить тяжёлые ingestion/generation процессы позднее.

## 2. Статус архитектурных утверждений

- **Подтверждено:** FastAPI, async SQLAlchemy, PostgreSQL/pgvector, aiogram и renderer уже присутствуют в репозитории.
- **Предлагается:** PWA, OIDC/session layer, RLS, Alembic, worker, object storage и workflow orchestration.
- **Не проверено:** доступность конкретных managed services и тарифов в текущем Railway account; выбор поставщика требует отдельной проверки без изменения production.

## 3. Контекст системы

```text
Преподаватель ── PWA/web ─┐
                          ├── API / policy boundary ── domain modules
Преподаватель ─ Telegram ─┘             │
                                        ├── PostgreSQL + pgvector
Редактор содержания ─ admin UI ─────────┤
                                        ├── object storage
                                        └── job queue ── worker
                                                           ├── ingest/OCR/embed
LLM/embedding/search providers ◀────────────────────────────┼── generate/verify
                                                           └── DOCX/PDF
```

Главная граница доверия находится в API, не в PWA, Telegram headers или тексте prompt. Worker получает подписанный внутренний job context; provider никогда не определяет владельца данных.

## 4. Физические компоненты пилота

| Компонент | Ответственность | Масштаб пилота |
|---|---|---|
| PWA | Диалог, курсы, preview/edit, документы, статусы job | 1 deploy, CDN/static hosting |
| FastAPI API | Session, authorization, orchestration, CRUD, signed downloads | 1–2 replicas без локального state |
| Worker | Ingest, OCR, embeddings, generation stages, LibreOffice | 1 replica, concurrency по ресурсам |
| Scheduler | Retention, stale jobs, source freshness, metrics rollup | один leader/cron |
| PostgreSQL | Транзакционные данные, RLS, FTS, pgvector | managed instance + backups |
| Queue | Надёжная доставка, retries, progress, cancellation | Redis или PostgreSQL queue |
| Object storage | Source revisions, exports, preview artifacts | private bucket, versioning/checksum |
| Identity provider | OIDC/OAuth2, invitation/MFA при необходимости | внешний либо self-hosted по решению |
| Observability | logs, traces, metrics, errors, cost | managed или совместимый стек |

**Предположение.** На Railway можно разместить API/worker/PostgreSQL/Redis, но object storage и identity должны выбираться по durability, backup, residency и стоимости, а не по удобству одного deploy. Существующий production не изменяется в рамках этого документа.

## 5. Модули backend

Предлагаемая структура не требует немедленного перемещения всех файлов. Сначала вводятся явные интерфейсы и запрет cross-module imports через внутренние детали.

| Модуль | Сущности/сервисы | Не должен делать |
|---|---|---|
| `identity` | User, Identity, Session, Membership, Role | Принимать user ID от обычного клиента как доказательство |
| `tenancy` | TenantContext, authorization policies, sharing grants | Строить доступ только на UUID secrecy |
| `courses` | Course, Class, progress, preferences, memory | Читать курс без owner/tenant predicate |
| `content` | Source, SourceRevision, rights, review, mapping | Активировать непроверенную ревизию |
| `ingestion` | UploadJob, extraction, OCR, structure, coverage | Удалять предыдущую approved revision при сбое |
| `retrieval` | eligibility, hybrid search, rerank, evidence set | Искать по withdrawn/private чужим источникам |
| `assistant` | intent, dialogue state, clarification, plan | Выполнять action до policy validation |
| `generation` | content map, scenario, artifact stages | Считать первый LLM response готовым материалом |
| `quality` | deterministic checks, evidence, task verifier, rubric | Скрывать failed checks |
| `documents` | preview model, DOCX/PDF revisions, signed access | Хранить доверенный путь из client input |
| `jobs` | state machine, retry/idempotency/progress | Делать бесконечные повторы |
| `audit` | append-only security/editorial events | Хранить секреты и полный sensitive payload |
| `channels` | web/Telegram adapters | Дублировать domain policy |

Существующие [app/services/retrieval.py](../app/services/retrieval.py), [app/services/grounded_generation.py](../app/services/grounded_generation.py), [app/services/docx_renderer.py](../app/services/docx_renderer.py) и domain catalogs являются исходными кандидатами для этих модулей.

## 6. Identity и session architecture

### 6.1. PWA

Рекомендуемый поток:

1. Пользователь переходит к identity provider по Authorization Code + PKCE.
2. Backend/BFF обменивает code и создаёт короткую server-side session.
3. Браузер получает `Secure`, `HttpOnly`, `SameSite=Lax/Strict` cookie; access token не хранится в `localStorage`.
4. Для изменяющих операций применяется CSRF protection, origin check и idempotency key.
5. Каждый request получает `Principal(user_id, tenant_id, roles, session_id)` только из проверенной session.

Конкретный provider выбирается ADR после проверки стоимости, российского правового контекста, export/delete возможностей и vendor lock-in.

### 6.2. Telegram

1. Авторизованный web-пользователь создаёт одноразовый короткоживущий link code.
2. Бот передаёт code через внутренний endpoint своим service credential.
3. Сервер связывает `telegram_user_id` с существующим `user_id`, code погашается.
4. Далее bot service credential и Telegram identity преобразуются сервером в principal.
5. Заголовок с произвольным user ID не принимается от внешнего клиента.

### 6.3. Роли

- `teacher`: только свои курсы, запросы, jobs, файлы и разрешённые глобальные источники;
- `content_editor`: staging/review/activation источников, без teacher private data;
- `admin`: пользователи, roles, limits, runtime; доступ к содержимому — только через support grant с audit;
- `service`: narrowly scoped worker/bot operations, без interactive login.

## 7. Tenant isolation и модель данных

### 7.1. Основные сущности

```text
tenant
  └─ membership ─ user ─ identity/session
       └─ course ─ class_group
            ├─ dialogue ─ message
            ├─ generation_request ─ generation_run ─ artifact_revision
            │                                  └─ export_revision
            └─ course_progress / preference

source ─ source_revision ─ source_page/section/chunk/embedding
  ├─ source_rights
  ├─ source_review
  └─ curriculum/topic/source_mapping
```

Глобальная курируемая библиотека имеет `scope=global`; пользовательский файл — `scope=tenant/private` и `owner_user_id`. Один физический row не должен одновременно означать глобальный и личный источник.

### 7.2. Обязательные поля

На teacher-owned таблицах:

- `tenant_id NOT NULL`;
- `owner_user_id NOT NULL` там, где есть личный владелец;
- `created_at`, `updated_at`, `deleted_at`/retention status;
- composite foreign keys, запрещающие связать run одного tenant с course другого;
- version/revision и optimistic lock для редактируемых данных.

### 7.3. Три слоя защиты

1. **Service policy:** repository получает `TenantContext`; метода без context нет.
2. **SQL constraints:** composite `(tenant_id, id)` foreign keys и tenant-scoped unique constraints.
3. **PostgreSQL RLS:** `SET LOCAL app.user_id/app.tenant_id` внутри транзакции; default deny policies; отдельная минимальная service role для migrations/worker.

RLS не заменяет service authorization, особенно для глобального content editor, но останавливает часть ошибок приложения. Connection pool должен очищать session state; предпочтительно `SET LOCAL` в транзакции.

### 7.4. Миграция существующих данных

1. Снять schema-only/обезличенный snapshot и backup.
2. Создать системного legacy owner/tenant.
3. Добавить nullable tenant columns.
4. Backfill детерминированным скриптом с отчётом counts/orphans.
5. Добавить composite indexes/FK.
6. Обновить приложение на dual-read/required context в staging.
7. Сделать columns `NOT NULL`.
8. Включить RLS сначала в staging, выполнить cross-tenant suite.
9. Провести restore rehearsal и только затем production release по отдельному разрешению.

## 8. Управление схемой

- Alembic — единственный production migration path.
- Каждая миграция имеет upgrade, описанный rollback/roll-forward и preconditions.
- Extensions (`uuid-ossp` при необходимости, `vector`) создаются/проверяются отдельной миграцией.
- Embedding dimension не маскируется cast-индексами: embeddings разделяются по model/revision/dimension или имеют согласованный column/index design.
- `AUTO_CREATE_TABLES` разрешён только в unit/dev bootstrap; production readiness требует `false`.
- Deploy выполняет `migration check → backup evidence → migrate job → schema smoke → app rollout`.

## 9. Источники и object storage

### 9.1. Неизменяемые ключи

Пример:

```text
sources/{source_id}/revisions/{revision_id}/original/{sha256}.pdf
sources/{source_id}/revisions/{revision_id}/derived/pages.json
exports/{tenant_id}/{run_id}/{export_revision_id}/teacher.docx
```

Ключ создаётся сервером. БД хранит storage provider/key/version, SHA-256, size, MIME и scan status, но не доверенный произвольный filesystem path.

### 9.2. Lifecycle ревизии

`uploaded → scanning → extracting → indexing → awaiting_review → approved` либо `failed/rejected/withdrawn`.

`Source.active_revision_id` переключается одной DB-транзакцией только после всех обязательных checks и редакционного approval. Старые ревизии остаются для воспроизводимости до retention decision. GenerationRun фиксирует точные source revision IDs и evidence snapshot.

### 9.3. Upload controls

- server-side MIME/signature validation;
- предел размера, страниц и decompression ratio;
- malware scan/quarantine;
- quota и concurrency;
- filename только как metadata;
- обработка в sandboxed worker без исходящих сетевых прав, если они не нужны.

## 10. Ingestion и полнота параграфа

Pipeline:

1. регистрация immutable upload;
2. проверка файла и прав;
3. text/layout extraction;
4. OCR для нужных страниц;
5. распознавание TOC, глав, параграфов, таблиц и подписей;
6. page-level completeness report;
7. структурные chunks с небольшим overlap и section path;
8. embeddings с `model`, `dimension`, `revision`, `created_at`;
9. тестовый retrieval/coverage report;
10. ручная проверка и activation.

Coverage выбранного параграфа оценивается по обязательным subtopics и диапазону страниц. Top-k retrieval остаётся способом ранжирования, но не заменяет выбор целого раздела, когда учитель просит полный урок по параграфу.

## 11. Retrieval и evidence model

### 11.1. Последовательность

1. Policy выбирает допустимые source revisions.
2. Query planner разбивает запрос на темы/подвопросы.
3. Exact curriculum/source mapping добавляет обязательные sections.
4. Hybrid FTS + vector search возвращает candidates.
5. Reranker сортирует в рамках разрешённого набора.
6. Coverage checker запрашивает недостающие subtopics.
7. Evidence builder создаёт immutable `EvidenceSet`.

### 11.2. EvidenceSet

Каждый item содержит:

- source/source_revision/chunk IDs;
- title, edition/status/year;
- PDF/print page, section path;
- точный text span и hash;
- source class и verification status;
- reason for selection;
- permissions (`quote_allowed`, `display_allowed`).

Ссылки генерации указывают не на «любой источник в manifest», а на evidence item/claim. При повторном открытии старого материала evidence сохраняется, даже если активная ревизия библиотеки изменилась.

### 11.3. Web и актуальные документы

- Official allowlist — только первый фильтр.
- Документ скачивается/фиксируется с датой и hash, определяется canonical publisher/version.
- Retrieved content рассматривается как данные, а не instructions.
- General web отключён для strict textbook, ФИПИ и действующего права.
- Источники с ограниченным сроком имеют `valid_from/valid_to/checked_at` и freshness job.

## 12. Многоэтапный assistant/generation workflow

```text
REQUESTED
  → INTERPRETED
  → NEEDS_CLARIFICATION | PLANNED
  → EVIDENCE_READY
  → CONTENT_MAP_READY
  → SCENARIO_READY
  → DRAFTED
  → VERIFIED
  → NEEDS_REVISION | READY_FOR_REVIEW
  → APPROVED_BY_TEACHER
  → RENDERED
```

Каждая стадия сохраняет вход, schema version, provider/model/prompt version, выход, latency, cost и error class. Повтор выполняется с той же idempotency key и не создаёт дубликатов.

### 12.1. Интерпретация

Deterministic parser извлекает надёжные сущности (класс, минуты, явно названный курс). Structured LLM parser дополняет intent/constraints. Validator сравнивает оба результата, course context и доступные источники. Существенная неопределённость переводит job в `NEEDS_CLARIFICATION`.

### 12.2. Content map

До prose формируется проверяемая карта:

- обязательные результаты/понятия;
- facts/causal links/examples;
- evidence item для каждого блока;
- план времени и student activities;
- age/level constraints;
- места, где данных недостаточно.

### 12.3. Сценарии

Method strategy является типизированным плагином: lecture, combined, practical, discussion/research, game, open lesson. Общий content map сохраняется, но activity graph и teacher/student actions реально отличаются. На пилоте достаточно трёх качественно проверенных стратегий; остальные вводятся по acceptance gate.

### 12.4. Проверка

Каскад:

1. Pydantic/schema and invariants;
2. source eligibility/reference integrity;
3. claim-to-evidence entailment;
4. dates/names/definitions consistency;
5. task answer/key/rubric verification;
6. duration and workload simulation;
7. age/method rubric;
8. comparison with golden expectations;
9. human review.

LLM reviewer может быть одним сигналом, но не единственным gate. На ошибке материал исправляется ограниченное число раз либо блокируется с понятным отчётом.

## 13. Jobs, retries и согласованность

Job хранит `tenant_id`, `owner_user_id`, type, state, idempotency key, input hash, attempt, progress, lease, deadline, cost budget и result IDs.

- exponential backoff только для retryable provider/network errors;
- validation/policy failures не повторяются автоматически;
- lease/heartbeat возвращает abandoned job в очередь;
- dead-letter status требует оператора;
- cancellation проверяется между стадиями;
- per-user/global concurrency и cost budgets;
- outbox pattern публикует job/event после DB commit;
- object upload сначала получает immutable key/checksum, затем DB record; orphan cleanup безопасен по grace period.

## 14. Документы

Существующий `python-docx` renderer сохраняется как адаптер. Вводится provider-neutral `DocumentModel`, чтобы preview и DOCX/PDF использовали одну структуру.

1. READY artifact получает revision.
2. Worker строит teacher/student DOCX в уникальные object keys.
3. LibreOffice запускается в изолированном worker process с CPU/memory/time limits.
4. PDF проходит open/page/text/visual smoke.
5. Checksums и sizes фиксируются в `ExportRevision`.
6. API выдаёт короткоживущий signed URL после owner check.

Никакой failed-quality artifact не получает статус готового экспорта. Перерендер создаёт новую revision.

## 15. PWA

**Предложение:** TypeScript + React/Next.js либо эквивалентный поддерживаемый стек; окончательный выбор — отдельный ADR и небольшой spike.

Страницы пилота:

- вход/приглашение;
- главная с conversational composer;
- clarification/job progress;
- preview/evidence/quality report;
- курсы и память;
- мои документы;
- настройки/удаление;
- ограниченный editor/admin library review.

PWA cache содержит static shell и явно сохранённые безопасные черновики. Authenticated API, полные учебники и приватные документы не кэшируются service worker без специально спроектированного encrypted/offline режима.

## 16. Observability и cost control

### 16.1. Correlation

`request_id → dialogue_id → job_id → generation_run_id → export_revision_id`. Эти идентификаторы присутствуют в logs/traces, но tenant/user отображаются pseudonymous IDs.

### 16.2. Метрики

- API latency/error by route/status;
- queue depth/age/retry/dead letters;
- provider latency/tokens/cost/failure;
- retrieval candidates/coverage/no-evidence;
- quality check failures;
- render duration/size/failure;
- database pool/locks/storage;
- auth failures/cross-tenant denied;
- pilot rating/correction rate.

### 16.3. Логи

Запрещены токены, cookies, API keys, полные документы и произвольные prompts по умолчанию. Для диагностического payload действует отдельный consent, encryption, role и retention.

## 17. Security architecture

| Риск | Контроль |
|---|---|
| IDOR/cross-tenant | principal + policy + composite FK + RLS + negative tests |
| Shared-key impersonation | персональная session, service credentials, one-time Telegram link |
| Prompt injection | content/instruction separation, policy outside LLM, restricted tools |
| Malicious PDF | quarantine, signature/limits/scan, sandbox worker |
| Forged source/page | immutable EvidenceSet, canonical metadata, claim references |
| Cost/DoS | rate/concurrency/token/search budgets, job cancellation |
| File traversal/tamper | server-generated object keys, checksum, signed URL |
| Secret leak | secret manager, log redaction, scanning, rotation runbook |
| Data loss | immutable revisions, backups/PITR, restore drills, outbox |
| Supply chain | lock file, dependency/image scan, pinned CI actions/images |

## 18. Deployment environments

- `local`: synthetic/no-secret data, disposable PostgreSQL/pgvector.
- `test/CI`: ephemeral DB and object store, migrations from zero and snapshot.
- `staging`: production-like, only synthetic or separately approved copied/obfuscated data.
- `production`: manual approval, protected branch/tag, migration gate, backup evidence.

Ключи, buckets, databases и identity clients разделены между окружениями. Production Railway не используется как test environment.

## 19. Architectural Decision Records

До реализации необходимо утвердить малые ADR:

1. identity/session provider;
2. tenant boundary и необходимость organization на пилоте;
3. Alembic migration/backfill/RLS strategy;
4. queue implementation;
5. object storage и residency/retention;
6. PWA stack/BFF model;
7. production embedding/reranker и dimension;
8. source rights/revision workflow;
9. LLM provider/data processing policy;
10. observability и privacy;
11. backup RPO/RTO;
12. подход к частичному переносу PR №8.

## 20. Эволюция из текущего проекта

Необходимая последовательность:

1. зафиксировать тестовый baseline и перенести безопасные CI/readiness improvements PR №8;
2. внедрить Alembic и восстановление;
3. добавить identity/tenant schema, backfill и RLS;
4. закрыть routes role policies;
5. заменить local mutable files на immutable object storage;
6. вынести тяжёлые процессы в jobs/worker;
7. версионировать источники/evidence;
8. внедрить multi-stage assistant/QA;
9. подключить PWA;
10. связать Telegram с web identity.

Детальные gates и порядок поставки — в [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md).
