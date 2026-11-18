# Целевая модель tenant-данных и безопасная миграция

**Статус:** проект, реализация не начата\
**Дата:** 2026-11-18\
**Зависимость:** migration foundation должен быть принят отдельно; production inventory и backfill требуют отдельного разрешения

## 1. Цель и инварианты

Tenant — обязательная граница безопасности между преподавателями и организациями. Для закрытого пилота **рекомендуется** персональный tenant на преподавателя: это решение ещё должен подтвердить владелец. Схема не должна исключать будущий organization tenant с несколькими membership.

Инварианты целевой модели:

1. Каждая приватная строка имеет обязательный `tenant_id`.
2. `owner_user_id` отражает стабильного владельца ресурса и не заменяет tenant boundary; автора операции отдельно фиксирует `created_by_user_id`/audit actor.
3. Tenant и owner не принимаются от клиента: их задаёт серверный `Principal`.
4. Связь child с parent другого tenant блокируется constraint-ом, а не только Python-кодом.
5. Application policy и PostgreSQL RLS применяются одновременно.
6. Отсутствующий DB tenant context означает нулевой доступ.
7. Runtime role не владеет таблицами и не имеет `BYPASSRLS`.
8. Глобальная проверенная библиотека отделена от частных источников; private-source rollout можно отложить до отдельного scope/revision design.
9. Файлы и фоновые задачи сохраняют ту же границу tenant, что и строки БД.
10. Legacy-строка без доказанного владельца изолируется от обычного API (например, через утверждённый quarantine-контур), а не назначается по догадке.

## 2. Подтверждённое состояние

В текущих моделях нет `tenant_id`, `User`, `Membership`, session или audit таблиц.

- [`Teacher`](../app/models/entities.py#L37-L49) — предметный профиль, а не login identity.
- `teacher_id` есть у `ClassGroup`, `ClassCourse`, `GeneratedMaterial` и опционально у `GenerationRun`: [`entities.py`](../app/models/entities.py#L52-L67), [`entities.py`](../app/models/entities.py#L121-L138), [`entities.py`](../app/models/entities.py#L292-L335).
- `Lesson`, `CurriculumProgress` и `Homework` получают владельца только транзитивно через `class_course_id`: [`entities.py`](../app/models/entities.py#L140-L195).
- У `ExportedFile`, `WebSearchRun` и `PilotFeedback` нет ни teacher, ни tenant: [`entities.py`](../app/models/entities.py#L338-L403).
- `Source` и дочерние `SourcePage`, `SourceSection`, `SourceChunk`, `SourceIngestionRun` не различают глобальный и tenant-private scope: [`entities.py`](../app/models/entities.py#L80-L119), [`entities.py`](../app/models/entities.py#L197-L289).
- Catalog и exam-модели являются общими справочниками и сейчас не имеют publish-границы на уровне доступа: [`catalog.py`](../app/models/catalog.py), [`exam.py`](../app/models/exam.py).
- Query в `MemoryService` фильтруются только по `class_course_id`, без tenant: [`app/services/memory.py`](../app/services/memory.py#L17-L49).
- Export lookup фильтруется только по UUID/run UUID: [`app/services/output_service.py`](../app/services/output_service.py#L137-L147).

Фактическое содержимое production PostgreSQL, роли, orphan-строки, объёмы и соответствие ORM в этой ветке не проверялись. Они остаются **непроверенными**.

## 3. Identity и организационные таблицы

Ниже логическая модель; точные PostgreSQL enum/check и индексы утверждаются в migration PR.

### `users`

| Поле | Назначение |
|---|---|
| `id UUID PK` | Внутренний стабильный ID |
| `status` | `invited`, `active`, `suspended`, `disabled` |
| `display_name` | Отображаемое имя |
| `locale`, `timezone` | Настройки UX |
| `authz_version` | Инвалидация sessions при смене полномочий |
| `created_at`, `updated_at`, `disabled_at` | Lifecycle |

### `user_identities`

Для OIDC identity хранит `user_id`, `issuer`, `subject`, snapshot проверенного email/name и timestamps. Пара `(issuer, subject)` логически уникальна. Email не является ключом и не объединяет аккаунты автоматически; имя таблицы не привязывает доменную модель к конкретному provider.

### `tenants`

`id`, `tenant_type` (`personal`/`organization`), `name`, `slug`, `status`, timestamps. `slug` — UX-идентификатор, не security boundary.

### `tenant_memberships`

`id`, `tenant_id`, `user_id`, `status`, timestamps; логически одна membership на пару `(tenant_id, user_id)`. В пилоте у пользователя ожидается один активный personal membership, если владелец утвердит эту модель, но схема допускает несколько tenant-ов.

Роль не следует хранить единственной строкой в `tenant_memberships`: пользователь может иметь несколько полномочий, а назначения нужно отзывать и аудировать независимо.

- `roles`: неизменяемый системный каталог с областью `tenant` или `platform`;
- `tenant_role_assignments`: membership, tenant-role, кто/когда выдал и отозвал;
- `platform_role_assignments`: user, platform-role, кто/когда выдал и отозвал.

Для пилота ожидаются tenant-роли `teacher`, `tenant_admin` и platform-роли `content_editor`, `platform_admin`. Platform-role сама по себе не даёт доступ к private tenant data. Service principal остаётся отдельным типом actor и не получает пользовательскую роль.

### Platform access

- `invitations`: digest token, ожидаемые issuer/email, tenant/role, expiry, redeemed/revoked timestamps.
- `sessions`, `oidc_login_transactions`: серверные auth-состояния из [`ADR_IDENTITY_AND_SESSION.md`](ADR_IDENTITY_AND_SESSION.md); выбранные session tenant/user обязаны соответствовать membership, статус которой перепроверяется на каждом запросе.
- `service_principals`, `service_credentials`: machine identity и scopes; credential хранится только как digest.
- `telegram_links`, `telegram_link_tokens`: связь канала и одноразовый linking.
- `support_access_grants`: tenant, platform actor, reason, scopes, expiry/revoke.
- `audit_events`: append-only security/administrative audit.

### `teacher_profiles`

Существующий `teachers` следует эволюционировать в предметный профиль:

```text
teacher_profiles
  id
  tenant_id            NOT NULL
  user_id              NOT NULL
  school_name
  default_lesson_duration
  timezone
  preferences
```

Профиль не аутентифицирует пользователя. Временное имя таблицы `teachers` можно сохранить на первом migration step, чтобы не объединять rename и tenant rollout. Уникальность `(tenant_id, user_id)` нельзя вводить до inventory: несколько legacy `Teacher` могут оказаться профилями одного человека. Безопасный переход допускает несколько profile ID одного membership и запрещает только cross-tenant/cross-owner связи.

## 4. Классификация существующих данных

### 4.1. Глобальные справочники

Читаются преподавателем только в опубликованном/утверждённом состоянии; меняются `content_editor` через review/publish workflow.

| Таблицы | Целевой scope |
|---|---|
| `subjects`, `grade_levels`, `courses` | global curated |
| `curricula`, `curriculum_units`, `topics` | global curated, published revision |
| `learning_outcomes`, `topic_outcomes` | global curated |
| `concepts`, `topic_concepts`, `skills`, `topic_skills` | global curated |
| `interdisciplinary_links`, `exam_links`, `topic_sources` | global curated |
| `exam_models`, `exam_resources`, `codifier_elements`, `exam_tasks`, `topic_exam_mappings` | global curated/FIPI provenance |

`review_status` уже существует на части catalog-таблиц, но само наличие поля не доказывает, что API исключает draft. Это должно стать явной policy.

### 4.2. Tenant-owned данные

| Таблица | Обязательные additions | Источник backfill |
|---|---|---|
| `teachers`/`teacher_profiles` | `tenant_id`, `user_id` | подтверждённая карта legacy teacher → invited user |
| `class_groups` | `tenant_id`, `owner_user_id` | teacher profile |
| `class_courses` | `tenant_id`, `owner_user_id` | согласованные teacher + class group |
| `lessons` | `tenant_id`, `owner_user_id` | class course |
| `curriculum_progress` | `tenant_id`, `owner_user_id` | class course |
| `homework` | `tenant_id`, `owner_user_id` | class course/lesson |
| `generated_materials` | `tenant_id`, `owner_user_id` | teacher/class course |
| `generation_runs` | `tenant_id`, `owner_user_id` | teacher/class course; `NULL` legacy — quarantine |
| `exported_files` | `tenant_id`, `owner_user_id` | generation run; standalone — quarantine |
| `web_search_runs` | `tenant_id`, `owner_user_id` | generation run; standalone — quarantine |
| `pilot_feedback` | `tenant_id`, `owner_user_id` | только доказанная identity/Telegram link |

На owner-owned строках пара `(tenant_id, owner_user_id)` должна ссылаться на существующую membership. Статус `active` проверяется policy/RLS: FK подтверждает существование membership, но не её runtime-статус. Membership не удаляется физически, пока на неё ссылаются данные; отзыв доступа выражается статусом.

`created_by_user_id` полезно отличать от текущего владельца. Если совместное редактирование появится позже, access моделируется явным grant/ACL, а не переписыванием `owner_user_id`. `tenant_admin` не получает неявное право читать материалы коллег.

### 4.3. Источники и embeddings

Private sources не являются обязательной частью identity/tenant migration. Для первого закрытого пилота безопаснее:

1. считать существующие `sources` и производные глобальным editorial-контуром только после проверки происхождения и прав;
2. разрешать преподавателю чтение лишь опубликованной/допустимой выборки;
3. запретить teacher-upload private sources до отдельной миграции scope/revisions;
4. не публиковать неоднозначные legacy sources и вынести их в editorial quarantine.

Будущий mixed-scope design должен различать `global_curated`, `tenant` и при необходимости `private owner`, согласовывая scope с nullable `tenant_id`/`owner_user_id`. Важные ограничения такого дизайна:

- текущие глобальные `source_key` и `file_hash` uniqueness нельзя механически переносить на private rows: нужны отдельная глобальная uniqueness и tenant-scoped uniqueness, не раскрывающие существование файла другого tenant;
- composite FK, содержащий nullable `tenant_id`, небезопасен как единственная гарантия: при PostgreSQL `MATCH SIMPLE` любой `NULL` пропускает проверку остальных колонок;
- поэтому для global/private parent-child связи нужно отдельно выбрать либо всегда non-null security namespace/scope ID, либо обычный FK на source и проверенную RLS/policy через parent; это решение требует benchmark и threat review;
- денормализация scope в pages/sections/chunks допустима только с механизмом, который доказывает его совпадение с parent и запрещает изменение scope после публикации.

Global source публикуется только после проверки provenance, прав и ingestion revision. Tenant/private source не становится частью глобального retrieval или `topic_sources` автоматически.

## 5. Composite constraints

UUID не является authorization control. Логический инвариант для каждого tenant parent — уникальная tenant-aware identity, а child обязан ссылаться на parent вместе с tenant. Точные имена constraints, порядок колонок и индексы определяются migration PR после inventory.

На owner-inherited цепочках одной пары `(tenant_id, parent_id)` недостаточно: связь должна также доказывать совпадение `owner_user_id`, либо иметь эквивалентный проверяемый инвариант. Это особенно важно внутри будущего organization tenant, где два преподавателя имеют одинаковый `tenant_id`.

Аналогично:

- `class_groups` → tenant/owner-compatible teacher profile;
- `class_courses` → class group и tenant/owner-compatible teacher profile;
- `lessons`, `curriculum_progress`, `homework` → owner-compatible class course;
- `homework` → lesson того же class course;
- `generated_materials` → owner-compatible teacher/class course/lesson;
- `generation_runs` → owner-compatible teacher/class course, если эти ссылки заданы;
- `exported_files`, `web_search_runs`, `pilot_feedback` → generation run того же tenant/owner, если ссылка задана;
- source child tables → `sources` по отдельно утверждённой global/private стратегии;
- tenant-private future dialogues/messages/jobs → их tenant parent.

Для optional relationship composite FK применяется только когда все его identifying columns заданы. Нужны отдельные логические checks вроде «`lesson_id` требует `class_course_id`», иначе `NULL` и `MATCH SIMPLE` обходят согласованность. Обычный FK только на UUID можно временно оставить во время перехода, но финальный gate требует tenant/owner-aware constraint и отсутствия противоречащих связей.

## 6. PostgreSQL RLS

### 6.1. DB roles

Минимальное разделение:

- `hsa_migrator`: owner DDL, не используется приложением;
- `hsa_app`: runtime, `NOSUPERUSER`, `NOBYPASSRLS`, не owner таблиц;
- отдельные worker roles только при реальной необходимости, также без общего bypass;
- read-only операционная роль с явными views/scopes, а не доступом ко всем таблицам.

### 6.2. Request context

После проверки principal контекст устанавливается в начале **каждой DB-транзакции**, а не один раз на HTTP-request. Один запрос может использовать несколько коротких транзакций; после каждого commit/rollback локальный контекст исчезает и должен быть установлен заново.

Контекст содержит как минимум trusted `tenant_id` и `user_id`, задаётся параметризованно transaction-local механизмом и берётся только из server-side principal. Session-level context запрещён: он может утечь следующему запросу через pool. Отсутствующий/невалидный principal не должен приводить к транзакции над private tables.

Текущие сервисы самостоятельно вызывают `commit()`, поэтому до RLS rollout нужен единый tenant-aware transaction boundary/repository helper. Длительный LLM/web/PDF-вызов не должен держать DB transaction открытым: состояние фиксируется короткой транзакцией до внешнего вызова и новой tenant-aware транзакцией после него. Роли из client payload или произвольного DB setting не участвуют в policy.

### 6.3. Политика private table

Для owner-owned таблицы и чтение, и запись концептуально требуют одновременно:

- row `tenant_id` равен trusted current tenant;
- row `owner_user_id` равен trusted current user;
- для пары tenant/user существует active membership;
- новая версия строки сохраняет те же tenant/owner значения.

Для действительно tenant-shared таблицы owner predicate может отсутствовать, но active membership остаётся обязательной. Такая классификация должна быть явной по таблицам; personal tenant пилота не является основанием ослаблять owner policy.

RLS включается и принудительно применяется к private tables. Runtime role не является их owner. Helper проверки membership, если используется, должен иметь фиксированный `search_path`, минимальные grants и не превращаться в общий data-access bypass.

Platform admin не получает постоянную bypass policy. Support-доступ активируется отдельным grant, scope/expiry которого проверяются сервером и аудитируются.

### 6.4. Global data

Teacher видит только `publication_status='published'`/эквивалентный approved state. `content_editor` получает write policy для review workflow, но не tenant-private rows. Для смешанной source-таблицы policy должна быть явным объединением published global read и own tenant read; не широким `OR role='admin'`.

## 7. Storage и async jobs

Tenant isolation не заканчивается в PostgreSQL.

- Object key: `tenants/<tenant_uuid>/exports/<opaque_uuid>`, не пользовательское имя и не абсолютный путь.
- В БД хранится storage key, size, checksum, status; путь не возвращается клиенту.
- Authorization выполняется до чтения metadata/файла.
- Job payload содержит trusted `tenant_id`, `requested_by_user_id`, immutable input IDs и idempotency key.
- Worker открывает tenant-aware транзакцию для каждого DB-этапа и повторно проверяет tenant/owner parent; service principal не получает `BYPASSRLS`.
- Temporary files создаются уникально, ограничиваются отдельным каталогом и удаляются при success/failure.
- Backup, object lifecycle и restore обязаны сохранять tenant mapping и audit continuity.

## 8. Безопасный backfill legacy-данных

Это план для staging rehearsal; он **не разрешает** операции в production.

### Gate 0. Решения и инвентаризация

1. Принять identity ADR и authorization matrix.
2. Выполнить read-only schema/data inventory: row counts, nulls, orphan FK, duplicate/contradictory teacher links, source origin/status, output paths.
3. Зафиксировать checksum inventory и schema revision.
4. Получить backup и доказать restore в отдельное окружение.
5. Владелец утверждает карту invited user ↔ legacy teacher. Классификация источников может выполняться отдельным editorial этапом и не должна блокировать identity migration, если private upload остаётся выключенным.

### Gate 1. Additive schema

1. Добавить identity/tenant/session/audit таблицы.
2. Добавить nullable `tenant_id`, `owner_user_id`/`user_id` и индексы в private tables.
3. Если владелец утвердил personal-tenant модель, создать personal tenants и memberships только для подтверждённых pilot users; иначе использовать отдельно утверждённое tenant mapping без изменения остальных инвариантов.
4. Для неоднозначных legacy rows подготовить изолированную quarantine strategy. Отдельный disabled tenant — рекомендуемый вариант, но конкретный способ утверждается после inventory; такие строки в любом случае не назначаются активному пользователю и недоступны обычному API.

### Gate 2. Детерминированный backfill

Порядок:

1. teacher profile;
2. class group;
3. class course с проверкой согласованности teacher/class;
4. lesson, progress, homework;
5. generated material и generation run;
6. export и web search run через generation run;
7. feedback только по уже доказанной identity link;
8. unresolved source ownership не выводить из filename/origin; оставить вне teacher-visible набора до отдельного editorial решения.

Каждое правило должно быть повторяемым и выдавать отдельные `mapped`, `quarantined`, `conflict` counts. Username, display name, email без подтверждения и клиентский `user_external_id` не являются доказательством владельца.

### Gate 3. Constraints

1. Отчёт должен показать ноль cross-tenant links.
2. Добавить composite unique/indexes.
3. Добавить composite FK сначала `NOT VALID`, затем `VALIDATE CONSTRAINT`.
4. После нулевых `NULL` поставить `NOT NULL` на private tenant fields.
5. Source scope constraints добавить только в отдельной миграции private sources; identity rollout не должен вводить неподтверждённую смешанную модель.

### Gate 4. Application cutover в staging

1. Principal обязателен для всех private queries.
2. Create-path не принимает owner/tenant от клиента.
3. Background jobs получают trusted context.
4. Сначала application authorization и cross-tenant tests; затем RLS.
5. Включить RLS/FORCE RLS в staging под реальной runtime role.
6. Выполнить connection pool, rollback/cancellation и direct SQL tests.

Dual-write без измеримого reconciliation не рекомендуется. Если переход требует временного legacy/read path, он работает только в staging, имеет срок удаления и сравнивает counts/IDs после каждого шага.

### Gate 5. Production change

Только отдельное разрешение владельца после:

- успешного staging rehearsal на восстановленной копии;
- утверждённого migration/rollback runbook;
- оценки lock/downtime и объёма backfill;
- полного backup/restore evidence;
- прохождения [`IDENTITY_TENANCY_ACCEPTANCE.md`](IDENTITY_TENANCY_ACCEPTANCE.md);
- назначенного оператора и окна наблюдения.

## 9. Rollback

До `NOT NULL`/RLS rollback — выключить новый application path в staging и оставить additive columns/tables; не удалять backfilled данные автоматически.

После enforcement rollback не должен означать снятие tenant защиты и возврат публичного API. Допустимый rollback:

1. остановить входящие private mutations;
2. вернуть предыдущую совместимую app-версию, которая понимает tenant fields;
3. отозвать sessions/service credentials при сомнении;
4. восстановить из проверенного backup только по отдельному incident decision;
5. сохранить audit и reconciliation report.

Разрушительное удаление колонок/tenant mapping в аварийном rollback запрещено.

## 10. Непроверенные вопросы и решения владельца

- Сколько реальных `Teacher` записей и можно ли однозначно сопоставить их 3–4 пилотным преподавателям.
- Есть ли exports/runs без teacher/class course и кому они принадлежат.
- Какие загруженные книги глобальные, какие частные, и какие права позволяют показывать полный текст страниц.
- Нужна ли видимость материалов коллег внутри будущего школьного tenant-а.
- Срок хранения private sources, запросов, feedback, outputs и audit.
- Реальные production DB roles, owner, `BYPASSRLS`, extensions и pool/proxy.
- Реальная файловая/object-storage топология и backup lifecycle.

Пока эти вопросы не закрыты, migration остаётся проектом, а production data не изменяются.
