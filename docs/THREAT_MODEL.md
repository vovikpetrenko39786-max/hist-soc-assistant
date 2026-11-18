# Модель угроз web/PWA, API, Telegram и образовательного контура

**Статус:** initial threat model для design review\
**Дата:** 2026-11-18\
**Метод:** активы и trust boundaries + сценарии STRIDE/abuse cases\
**Scope:** текущий `main` и предлагаемая многопользовательская архитектура

## 1. Резюме

Закрытый многопользовательский пилот нельзя запускать на текущей модели доступа. Blocker-риски: отсутствие пользовательской аутентификации, IDOR и tenant isolation, открытые ingestion/embedding/raw-source endpoint-ы, подмена Telegram identity, неограниченный расход внешних API и скачивание экспортов по UUID.

Приоритет защиты:

1. deny-by-default identity и route policy;
2. tenant/owner model, composite FK и RLS;
3. scoped service identity и привязка Telegram;
4. изоляция source ingestion/output conversion;
5. quota, audit, data minimization и эксплуатационные контроли.

Эта модель не подтверждает состояние Railway, production PostgreSQL, TLS, backups, secret rotation или внешних provider contracts. Они перечислены как непроверенные.

## 2. Подтверждённые факты текущего кода

- Router-ы `/api/v1` подключаются без auth dependency: [`app/main.py`](../app/main.py#L25-L38); [`get_session`](../app/api/deps.py#L8-L10) выдаёт только DB session.
- Shared `X-Admin-Key` защищает только загрузку книги, список feedback и stats: [`admin_library.py`](../app/api/routes/admin_library.py#L21-L49), [`pilot.py`](../app/api/routes/pilot.py#L17-L21). Персональной атрибуции и ролей он не даёт.
- Без auth доступны replacement ingestion, embedding, generation, web search, lesson mutation, raw source pages, render и downloads; полный перечень — в [`AUTHORIZATION_MATRIX.md`](AUTHORIZATION_MATRIX.md).
- Tenant model отсутствует, а ownership неполон: [`app/models/entities.py`](../app/models/entities.py#L37-L403).
- Telegram передаёт identity-like значения обычным JSON `client_context`; service credential между ботом и backend отсутствует: [`telegram_bot/main.py`](../telegram_bot/main.py#L36-L44), [`telegram_bot/api_client.py`](../telegram_bot/api_client.py#L24-L36).
- `TELEGRAM_ADMIN_IDS` есть в settings, но code search не обнаруживает его применения; bot обрабатывает сообщения любого пользователя и допускает concurrency 20: [`config.py`](../app/core/config.py#L69-L75), [`telegram_bot/main.py`](../telegram_bot/main.py#L219-L243).
- Feedback доверяет присланным `user_external_id`, username и `generation_run_id`: [`pilot.py`](../app/api/routes/pilot.py#L24-L43).
- Export скачивается только по UUID, а response schema содержит внутренний `file_path`: [`outputs.py`](../app/api/routes/outputs.py#L33-L49), [`app/schemas/output.py`](../app/schemas/output.py#L31-L47).
- `OutputRenderRequest` принимает произвольный inline artifact; auth, owner quota и rate limit на route отсутствуют: [`output.py`](../app/schemas/output.py#L11-L28), [`outputs.py`](../app/api/routes/outputs.py#L22-L30).
- `GenerationRun` сохраняет request/context/output, а `WebSearchRun` — query/answer/source list; policy retention не найдена: [`entities.py`](../app/models/entities.py#L311-L382).
- Web request позволяет `scope='general'` и по умолчанию `force_search=True`: [`app/schemas/web_knowledge.py`](../app/schemas/web_knowledge.py#L5-L12).
- PDF ingestion проверяет расширение имени и пишет весь upload до вычисления размера; явного лимита bytes/pages/CPU здесь нет: [`source_ingestion.py`](../app/services/source_ingestion.py#L55-L87).
- Re-ingestion удаляет существующие chunks/sections/pages до создания новых производных данных: [`source_ingestion.py`](../app/services/source_ingestion.py#L124-L145). Стабилизационный PR рассматривается отдельно и не считается частью `main`.
- LibreOffice запускается с timeout, но Dockerfile не задаёт non-root user или resource limits: [`pdf_export.py`](../app/services/pdf_export.py#L18-L53), [`Dockerfile`](../Dockerfile#L1-L19).
- Workflow возвращает клиенту `str(exc)`: [`workflow.py`](../app/api/routes/workflow.py#L21-L29).
- Большая часть Python dependencies задана диапазоном/без точной версии, lock/hash-файл не обнаружен: [`pyproject.toml`](../pyproject.toml#L6-L29).

## 3. Критичные активы

| Актив | Почему критичен |
|---|---|
| Users, memberships, roles, sessions, Telegram links | Позволяют действовать от имени преподавателя/администратора |
| Классы, уроки, прогресс, feedback, preferences | Персональные и профессиональные данные преподавателя |
| Запросы, generation runs, DOCX/PDF | Могут содержать внутренние материалы, заметки и историю работы |
| Учебники, извлечённые страницы, chunks, embeddings | Авторские права, целостность знаний, возможный полный текст |
| Catalog, программы и ФИПИ mappings | Основание образовательной корректности и provenance |
| DB/OpenAI/embedding credentials, Telegram token, session secrets | Компрометация backend/провайдеров и расходы |
| Внешний API-бюджет и compute/storage | Возможен финансовый/ресурсный DoS |
| Audit, backups, restore artifacts | Расследование, восстановление и доказательство изоляции |

Student PII не должен попадать в систему без отдельной product/legal модели. Нынешнее поле `students_count` не требует student identities; это следует сохранить как принцип пилота.

## 4. Trust boundaries

1. PWA/browser ↔ public ingress/API.
2. OIDC provider ↔ auth callback/session subsystem.
3. Telegram user ↔ Telegram platform ↔ bot.
4. Telegram bot ↔ backend API.
5. API/worker ↔ PostgreSQL и connection pool.
6. API/worker ↔ source/output filesystem или object storage.
7. Backend ↔ LLM, embeddings и web-search providers.
8. Backend ↔ PyMuPDF/LibreOffice subprocess.
9. Content editor ↔ global library/review workflow.
10. Platform admin/support ↔ tenant-private data.
11. Runtime ↔ logs/metrics/backups/CI artifacts.

Данные из браузера, Telegram `client_context`, PDF, web, textbook text и LLM output считаются недоверенными. «Официальный домен» повышает provenance, но не превращает содержимое в executable instruction.

## 5. Реестр угроз

| ID / приоритет | Сценарий | Последствие | Обязательный контроль | Остаточный риск |
|---|---|---|---|---|
| T01 Blocker | Любой вызывает открытый API | Имитация преподавателя, mutations, расходы | OIDC+BFF session, invitation-only, deny-by-default | Захват аккаунта IdP |
| T02 Blocker | IDOR по UUID/run/course/export | Чтение/изменение чужих данных | Resource policy + mandatory tenant/owner + composite FK + RLS | Ошибка в новой policy; покрывается negative tests |
| T03 Blocker | Публичный ingest/embed заменяет/портит индекс | Потеря/подмена источника, CPU/disk DoS | CE/service only, immutable revision, quarantine, atomic publish, audit | Parser/worker failure |
| T04 Blocker | Клиент подставляет чужой Telegram ID | Действия/файлы от имени другого teacher | One-time linking + authenticated scoped bot service | Компрометация bot credential |
| T05 Blocker | Массовые assistant/web/render calls | Финансовый, CPU, storage DoS | User/tenant/global quota, concurrency, idempotency, budget cutoff | Распределённая атака/ошибка расчёта цены |
| T06 Blocker | Raw pages/exports доступны по UUID | Утечка материалов/авторского текста | Authorize before metadata/file; raw page only editorial; licensed snippets | Неверная rights classification |
| T07 High | Общий admin key украден/переиспользован | Неатрибутируемый privileged access | Human roles, MFA, sessions, audit; убрать shared key | Privileged account compromise |
| T08 High | RLS context остаётся в pooled connection | Запрос B видит tenant A | Только `SET LOCAL` в transaction, app role no bypass, reuse/rollback tests | Ошибка драйвера/config |
| T09 High | Child ссылается на parent другого tenant | Скрытая cross-tenant связь/утечка | Composite FK `(tenant_id, id)` | Ошибка классификации global/private |
| T10 High | Oversized/corrupt/exploit PDF | CPU/RAM/disk exhaustion, parser compromise | Magic/MIME/size/page limits, sandbox worker, no network, time/resource caps | Zero-day parser |
| T11 High | Prompt injection в PDF/web | Ложные citations, искажение урока, попытка tool abuse | Контент как data, фиксированные tools/policies, provenance, output validation | Семантическое влияние на качество |
| T12 High | Storage path/symlink/TOCTOU | Чтение/выдача чужого или системного файла | Opaque object keys, tenant namespace, containment, no symlink, checksum | Компрометация storage/DB вместе |
| T13 High | Provider получает лишние prompts/context | Утечка персональных/лицензионных данных | Data minimization/redaction, DPA/retention decision, no student PII | Provider/legal risk |
| T14 High | Злоупотребление admin/support | Скрытый просмотр tenant data | Нет постоянного bypass; JIT support grant, reason, TTL, audit | Collusion/compromised audit |
| T15 Medium | CSRF/session fixation после PWA | Mutation/hijack session | State/nonce/PKCE, rotation, HttpOnly Secure SameSite, CSRF+Origin | XSS в same origin |
| T16 Medium | XSS через user/LLM content | Захват действий пользователя | CSP, escaping/sanitization, no raw HTML, no browser token storage | Browser/extension compromise |
| T17 Medium | Secrets/PII в error/log/metrics | Credential/data disclosure | Stable errors, structured redaction, no prompt/token labels | Ошибка сторонней библиотеки |
| T18 Medium | Supply-chain/root container compromise | Захват app, secrets, storage | Lock/hashes, SBOM/scans, non-root, read-only FS, minimal egress | Dependency zero-day |
| T19 Medium | Backup/restore смешивает tenant/теряет RLS | Массовая утечка или потеря данных | Encrypted scoped backups, restore rehearsal, post-restore RLS/constraint tests | Backup operator compromise |
| T20 Medium | Race/replay создаёт повторные runs/links | Двойные расходы или takeover link | Unique idempotency, row lock, token digest/single-use/TTL | Cross-region timing |
| T21 Medium | Draft/unverified catalog виден teacher | Методические ошибки и ложная официальность | Publish states enforced in query/RLS, editorial separation | Ошибка редактора |
| T22 Medium | Нет retention/deletion | Избыточный объём чувствительных данных | Owner-approved retention, lifecycle job, legal hold procedure | Потеря полезной диагностики |

## 6. Архитектурные контроли

### Identity и authorization

- OIDC Authorization Code + PKCE через backend; opaque server sessions.
- `Principal` только из проверенной session/service credential.
- Route policy registry и deny-by-default для всего `/api/v1`.
- Personal tenant на преподавателя в пилоте.
- Platform roles не наследуют private tenant read.
- Support access только отдельным временным grant.

Подробности: [`ADR_IDENTITY_AND_SESSION.md`](ADR_IDENTITY_AND_SESSION.md) и [`AUTHORIZATION_MATRIX.md`](AUTHORIZATION_MATRIX.md).

### Database и storage

- Mandatory `tenant_id`, server-derived owner, composite FK, RLS/FORCE RLS.
- Runtime role не owner/no `BYPASSRLS`; migration role отдельно.
- Storage key с tenant namespace и opaque ID; никакого client-visible `file_path`.
- Authorize до `stat/open`, затем containment, status, size и checksum.
- Audit append-only для security/privileged operations.

Подробности: [`TENANT_DATA_MODEL.md`](TENANT_DATA_MODEL.md).

### Источники и generation

- Для пилота редактор ведёт общую библиотеку утверждённых изданий. Включение личных загрузок требует отдельной проверки прав на файл, метаданные, фрагменты и результаты векторного поиска. [Модель хранения источников](TENANT_DATA_MODEL.md).
- Upload → quarantine → type/size/page scan → isolated parse → review → immutable publish.
- Published revision не заменяется до полного успеха новой revision.
- Retrieval scope строит сервер; teacher не расширяет statuses/archive/source scope.
- LLM не принимает решения об identity, roles, tools или source publication.
- Citation/provenance и педагогические quality gates остаются deterministic server controls.
- Quality-failed result не экспортируется пользователю как готовый материал.

### Operations

- Limits per IP/user/tenant/operation и общий daily provider budget.
- Idempotency key для generation/render/ingestion.
- Non-root containers, CPU/RAM/pids/time limits, ограниченный egress worker-ов.
- Secrets только в managed secret store; rotation/revoke rehearsal.
- Структурированные redacted logs с correlation ID, без token/full prompt.
- Dependency lock/hashes, SBOM и vulnerability gate.

## 7. Обязательные security gates до пилота

1. Все 35 `/api/v1` endpoint-ов имеют явную policy; anonymous получает `401`.
2. Два tenant-а проходят cross-tenant HTTP и direct SQL negative tests по всем private resource types.
3. RLS остаётся fail-closed после commit, rollback, exception, timeout, cancellation и connection reuse.
4. Session tests покрывают OIDC validation, fixation, rotation, revoke, expiry, CSRF и Origin.
5. Привязка Telegram проходит через личный чат и подтверждение в исходной веб-сессии. Тесты проверяют подмену идентификатора, одноразовость кода, истечение срока, отзыв связи и ограничения прав бота.
6. Teacher не может ingest/embed/publish/raw-read; CE не может читать private teacher data; PA требует support grant.
7. Oversized/corrupt/fake/high-page/parser-crash PDF не меняют published revision и не исчерпывают worker.
8. Quota/concurrency/budget отклоняют запрос **до** OpenAI/embedding/LibreOffice.
9. Cross-tenant export, traversal, symlink, checksum mismatch и missing file fail closed.
10. Prompt-injection corpus не влияет на auth/tools, не раскрывает другой tenant и не создаёт неподтверждённые citations.
11. Автоматический secret scan HTTP errors/logs/audit не находит token, cookie, DB URL и полный private content.
12. Backup/restore rehearsal сохраняет tenant constraints, RLS и audit continuity.
13. Runtime container запускается non-root; нет непринятых critical dependency/container findings.

Полный исполнимый перечень: [`IDENTITY_TENANCY_ACCEPTANCE.md`](IDENTITY_TENANCY_ACCEPTANCE.md).

## 8. Остаточные риски для формального принятия

Даже после внедрения остаются:

- захват учётной записи/сессии пользователя или IdP outage;
- злоупотребление platform admin и компрометация нескольких control planes;
- zero-day PyMuPDF/LibreOffice/dependency;
- компрометация официального сайта или ошибочный официальный документ;
- hallucination/методическая ошибка модели при корректных ссылках;
- отказ или изменение поведения LLM/search/embedding provider;
- человеческая ошибка при rights/source classification;
- потеря доступности PostgreSQL/object storage.

Для пилота residual risk принимается владельцем письменно после доказательств gates, а не только по наличию кода.

## 9. Непроверенные компоненты

По репозиторию нельзя подтвердить:

- внешний ingress, TLS, WAF, private networking и фактическую экспозицию Railway;
- production DB roles/owner/`BYPASSRLS`, encryption at rest и connection proxy;
- backup frequency, encryption, retention и успешные restore tests;
- доступ операторов, secret store, rotation history и incident process;
- реальные централизованные logs/metrics и redaction;
- object storage/lifecycle (текущий код использует локальные paths);
- provider DPA, regionality, training/retention settings;
- выбранный OIDC provider, MFA и invitation/recovery policy;
- юридические права на полный текст каждого учебника и его выдачу через API.

Эти пункты должны быть закрыты evidence-артефактами владельца/оператора до production rollout; эта ветка их не изменяет и не проверяет через production access.
