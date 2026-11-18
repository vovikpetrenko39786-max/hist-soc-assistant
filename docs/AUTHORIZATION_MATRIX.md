# Матрица авторизации API

**Статус:** предложена для утверждения до реализации
**Дата:** 2026-11-18
**Scope:** 35 явно объявленных операций `/api/v1` текущего `main`, отдельный `GET /health` и явно отделённые будущие auth/bootstrap endpoint-ы

## 1. Условные обозначения

| Обозначение | Principal |
|---|---|
| Public application endpoint | Без principal; только минимальная техническая информация, не данные продукта |
| T | Активный `teacher` membership текущего tenant-а |
| TA | `tenant_admin` текущего tenant-а |
| CE | Platform role `content_editor` |
| PA | Platform role `platform_admin` |
| S(scope) | Service principal с указанным узким scope |
| Support | PA с отдельным действующим support grant для конкретного tenant/resource |

### 1.1. Public application API и auth bootstrap — разные поверхности

- **Public application/data API** — route, который анонимный клиент может использовать без предварительной security-транзакции. В закрытом пилоте таких `/api/v1` route-ов нет.
- `GET /health` — отдельный public operational endpoint с минимальной схемой; он не является API доступа к продуктовым данным.
- Будущие `GET /auth/login` и `GET /auth/callback` доступны без уже созданной session только как **unauthenticated auth bootstrap**. Первичный enrollment требует invitation transaction; уже известный active `(issuer, subject)` может использовать обычную login transaction без нового invitation. Bootstrap не возвращает catalog или пользовательские данные и не даёт общий anonymous-доступ.
- `/auth/session`, accept invitation, logout и все product/channel/admin route-ы требуют установленную ограниченную либо обычную session и не относятся к public data API.
- Swagger/OpenAPI UI не является auth bootstrap и не получает исключение из deny-by-default.

Базовые правила:

- deny-by-default: новый route без зарегистрированной policy не запускается;
- без session/service credential защищённый route возвращает `401`;
- недостаточная роль возвращает `403`;
- чужой или недоступный tenant-resource возвращает `404`, не раскрывая существование;
- `tenant_id`, `user_id`, `teacher_id`, `owner_user_id`, role и `user_external_id` из payload/header не определяют principal;
- `GET /health` — единственное public application/operational исключение закрытого пилота; auth bootstrap учитывается отдельным allowlist;
- browser mutation требует CSRF и допустимый `Origin`;
- rate/quota и audit являются частью policy для затратных/привилегированных операций.

## 2. Допущения закрытого пилота

Это проектные допущения, а не подтверждение состояния production. Они должны быть письменно утверждены владельцем до реализации:

- первичный enrollment пилота invitation-only для 3–4 совершеннолетних преподавателей; существующий active user может повторно войти через OIDC без нового invitation; student accounts и student PII отсутствуют;
- каждому преподавателю создаётся персональный tenant и одна активная membership; school tenant, tenant switch, teacher-to-teacher sharing и доступ `tenant_admin` к содержимому в пилот не входят;
- классы, уроки, запросы, generation runs, feedback и exports доступны только владельцу; support-доступ выдаётся отдельно, на срок и с audit;
- PWA и backend работают как same-origin BFF с server session; anonymous catalog/generation и bearer token в JavaScript не допускаются;
- PWA пилота не предоставляет offline-режим для персональных данных и документов; offline cache разрешён только для обезличенных versioned static assets;
- библиотека пилота глобальная и curated; teacher upload/private source publication отложены, ingest и индексация доступны только `content_editor`/library worker;
- Telegram работает только для заранее приглашённого пользователя после server-side linking и явного подтверждения pending link в PWA; Telegram ID и `client_context` сами по себе не создают principal;
- низкоуровневые generation/retrieval/render/web route-ы не вызываются браузером и доступны только раздельным service principals;
- значения session TTL, retention, OIDC provider, rights policy учебников и provider budgets остаются отдельными решениями владельца.

Если любое допущение меняется, matrix и acceptance tests пересматриваются до расширения пилота.

## 3. Подтверждённый текущий режим

Router-ы подключаются без общей auth dependency в [`app/main.py`](../app/main.py#L25-L38). [`get_session`](../app/api/deps.py#L8-L10) не выполняет auth.

В `main` явно объявлены **35 операций `/api/v1`**:

| Семейство | Число операций |
|---|---:|
| `router` | 1 |
| `class-courses` | 1 |
| `lessons` | 2 |
| `catalog` | 4 |
| `exams` | 5 |
| `sources` | 5 |
| `retrieval` | 2 |
| `generation` | 1 |
| `pedagogy` | 1 |
| `outputs` | 4 |
| `assistant` | 2 |
| `pilot` | 4 |
| `admin/library` | 1 |
| `web` | 2 |
| **Итого `/api/v1`** | **35** |

Отдельно явно объявлен `GET /health`; таким образом, в прикладном коде есть 36 явных method/path операций. Будущие route-ы раздела 5 в этот baseline не входят. Поскольку `FastAPI(...)` в [`app/main.py`](../app/main.py#L22) не переопределяет стандартные docs URL, framework также регистрирует `/openapi.json`, `/docs`, `/docs/oauth2-redirect` и `/redoc`; production должен отключить их либо защитить отдельной environment policy.

Единственные локальные проверки shared key среди 35 `/api/v1` операций:

- `POST /api/v1/admin/library/books` — `X-Admin-Key` в [`admin_library.py`](../app/api/routes/admin_library.py#L21-L49);
- `GET /api/v1/pilot/feedback` и `GET /api/v1/pilot/stats` — тот же тип проверки в [`pilot.py`](../app/api/routes/pilot.py#L17-L21).

Остальные **32 из 35** `/api/v1` операций не имеют code-level auth/RBAC/tenant policy. `GET /health` также открыт намеренно. Shared key не считается identity и должен быть удалён после перехода на роли.

## 4. Целевая матрица текущих endpoint-ов

### System, routing и workflow

| Method/path | Целевой доступ | Resource/условия | Дополнительный контроль |
|---|---|---|---|
| `GET /health` | Public | Только `{status}` без provider/model/config | Rate limit; отдельный internal readiness |
| `POST /api/v1/router/preview` | Disabled; временно S(`router.preview`) | Legacy stateless parser; убрать после миграции на assistant preview | Не публиковать браузеру; не вызывать внешние API |
| `POST /api/v1/assistant/preview` | T; при необходимости S(`assistant.preview_for_linked_user`) | План для текущего principal/linked user | Не доверять `client_context`; per-user limit |
| `POST /api/v1/assistant` | T; S(`assistant.invoke_for_linked_user`) | Run создаётся с server-derived tenant/owner | Quota, concurrency, idempotency, audit, cost budget |

Telegram service scope действует только после server-side mapping Telegram link → active user/membership. Service не выбирает произвольного user.

### Классы и уроки

| Method/path | Целевой доступ | Resource/условия | Дополнительный контроль |
|---|---|---|---|
| `GET /api/v1/class-courses/{class_course_id}/context` | T, Support | В пилоте только owner; school sharing требует отдельной будущей policy | Все вложенные lessons/progress/homework с тем же tenant |
| `POST /api/v1/lessons` | T | `class_course_id` текущего tenant и доступен teacher | Tenant/owner только из principal; composite FK |
| `POST /api/v1/lessons/{lesson_id}/complete` | T | Lesson текущего tenant и доступен teacher | Optimistic version/idempotency; audit mutation |

### Catalog и экзамены

В закрытом пилоте даже read-only catalog требует login. Это упрощает public surface и не мешает позднее открыть отдельные обезличенные справочники.

| Method/path | Целевой доступ | Resource/условия |
|---|---|---|
| `GET /api/v1/catalog/subjects` | T, CE, PA | Только active/published |
| `GET /api/v1/catalog/curricula` | T, CE, PA | Teacher видит published; CE видит draft по явному filter/policy |
| `GET /api/v1/catalog/topics/search` | T, CE, PA | Teacher видит published |
| `GET /api/v1/catalog/topics/{topic_id}` | T, CE, PA | Teacher видит published; недоступный draft → `404` |
| `GET /api/v1/exams/models` | T, CE, PA | Только approved/current для teacher |
| `GET /api/v1/exams/models/{model_key}` | T, CE, PA | Та же publish policy |
| `GET /api/v1/exams/models/{model_key}/tasks` | T, CE, PA | Та же publish policy |
| `GET /api/v1/exams/models/{model_key}/codifier` | T, CE, PA | Та же publish policy |
| `GET /api/v1/exams/topics/{topic_id}/mappings` | T, CE, PA | Published topic/model only |

### Источники и retrieval

| Method/path | Целевой доступ | Resource/условия | Дополнительный контроль |
|---|---|---|---|
| `GET /api/v1/sources` | T, CE, PA | Пилот T: только published global metadata; own tenant-private — лишь после отдельного feature rollout | Не раскрывать storage path/licensing internals |
| `POST /api/v1/sources/resolve-preview` | T, CE | В пилоте только разрешённые published global sources | Per-user limit; private scope включается отдельной policy |
| `POST /api/v1/sources/{source_id}/ingest` | CE; S(`sources.ingest`) | CE: draft global или явно разрешённый source; service job bound к source scope | Size/type/page limits, quarantine, isolated worker, audit |
| `GET /api/v1/sources/{source_id}/ingestion-status` | CE; S(`sources.status.read`) | Только доступный source/job | Не раскрывать внутренний path/error secrets |
| `GET /api/v1/sources/{source_id}/pages/{page_number_pdf}` | CE; S(`sources.read_raw`) | Raw page только для review/processing | Teacher получает отдельный licensed citation/snippet view, если разрешено правообладателем |
| `POST /api/v1/retrieval/search` | CE; S(`retrieval.search`) | Published global + tenant scope effective user | Внешний teacher API использует `/assistant`, не raw retrieval |
| `POST /api/v1/retrieval/sources/{source_id}/embed` | CE; S(`sources.embed`) | Только доступная immutable ingestion revision | Quota/concurrency, model/dimension check, audit |
| `POST /api/v1/admin/library/books` | CE; S(`sources.import`) | Создаёт draft/import job, не live published source | Заменить `X-Admin-Key`; malware/rights/review gate; audit |

Текущее сообщение «книга добавлена в live library» в [`admin_library.py`](../app/api/routes/admin_library.py#L95-L105) не соответствует целевому review/publish gate и не должно сохраняться в production flow.

### Генерация и controlled web

Низкоуровневые endpoint-ы не нужны браузеру пилота: orchestration уже выполняется через `/assistant`. Их следует сделать internal/service-only либо убрать из внешнего router. Если позднее их откроют PWA, они обязаны получить **ровно те же** tenant, quota, provenance и audit policies.

| Method/path | Целевой доступ пилота | Resource/условия | Дополнительный контроль |
|---|---|---|---|
| `POST /api/v1/generation/lesson` | S(`generation.run`) | Effective tenant/user закреплены сервером | Budget, idempotency, source publish policy, audit |
| `POST /api/v1/pedagogy/generate` | S(`generation.run`) | То же | То же; quality failure не экспортируется |
| `POST /api/v1/web/search` | S(`web.search`) | Запрос от уже авторизованного run; tenant policy | Allowlisted official domains, daily budget, no arbitrary force override |
| `GET /api/v1/web/official-domains` | T, CE; S(`web.policy.read`) | Stateless policy preview | Не раскрывает credentials; rate limit |

### Outputs

| Method/path | Целевой доступ | Resource/условия | Дополнительный контроль |
|---|---|---|---|
| `GET /api/v1/outputs/templates` | T, CE | Только опубликованные templates | Без локальных path |
| `POST /api/v1/outputs/render` | S(`outputs.render`) | Run/artifact effective user; quality passed | Quota, sandbox converter, storage tenant namespace, audit |
| `GET /api/v1/outputs/files/{export_id}` | T, Support; S(`exports.download_for_linked_user`) | Export текущего tenant/owner; service только on-behalf-of linked user | Authorize до metadata/path, checksum/containment, download audit |
| `GET /api/v1/outputs/runs/{run_id}` | T, Support | Run текущего tenant/owner | List не раскрывает чужие file names/checksums/counts |

### Pilot и operations

| Method/path | Целевой доступ | Resource/условия | Дополнительный контроль |
|---|---|---|---|
| `POST /api/v1/pilot/feedback` | T; S(`feedback.create_for_linked_user`) | `user_id`, tenant и run server-derived; run доступен user | Не принимать identity из payload; rate limit |
| `GET /api/v1/pilot/feedback` | PA; CE только content-error queue; Support при конкретном case | Минимальные поля по назначению | PII minimization, audit, pagination |
| `GET /api/v1/pilot/stats` | PA | Агрегаты без лишней PII; tenant filter при необходимости | Заменить shared key, audit privileged query |
| `GET /api/v1/pilot/health` | PA/operations; S(`operations.readiness`) | Не public | Убрать сведения о provider/model/config из внешнего ответа |

### 4.1. Внутренние service principals и scopes

Scope всегда связан с конкретным `service_principal`, `audience` и окружением. Один credential не объединяет все строки таблицы.

| Service principal | Разрешённые scopes пилота | Дополнительная граница |
|---|---|---|
| Telegram gateway | `telegram.link.redeem`, `assistant.preview_for_linked_user`, `assistant.invoke_for_linked_user`, `feedback.create_for_linked_user`, `exports.download_for_linked_user` | Effective user только через active server-side Telegram link; произвольный `user_id` запрещён |
| Generation worker | `generation.run`, `retrieval.search`, `web.search`, `web.policy.read`, `outputs.render` | Job содержит неизменяемые tenant/user/run IDs и подписанный либо одноразовый job capability |
| Library worker | `sources.import`, `sources.ingest`, `sources.status.read`, `sources.read_raw`, `sources.embed` | Только source/revision из editorial job; публикация требует отдельного human review |
| Internal monitor | `operations.readiness` | Только readiness/metrics schema без product data и secrets |
| Temporary router diagnostic | `router.preview` | Только non-production либо time-limited rollout; затем route удаляется |

Service credential:

- имеет отдельные `iss/sub/aud`, expiry и revoke/rotation lifecycle;
- не получает human role, browser cookie, общий tenant bypass или `BYPASSRLS`;
- не расширяет scope через payload/header;
- для delegated action фиксирует одновременно service actor и effective user в audit;
- для worker action принимает resource scope только из серверной job, а не из произвольного caller UUID;
- service-only route не принимает browser cookie principal, не включается в browser CORS и по возможности отсутствует на public ingress.

## 5. Предлагаемые auth/channel endpoint-ы

Эти route-ы отсутствуют в `main`, не входят в текущие 35 `/api/v1` операций и не являются выполненной реализацией. Будущий контракт ниже содержит 12 операций: 6 под `/auth`, 5 под `/api/v1` и 1 под `/internal`.

| Method/path | Доступ | Назначение/контроль |
|---|---|---|
| `GET /auth/login` | Unauthenticated bootstrap | Начать invitation enrollment либо existing-user login transaction; state/nonce/PKCE; allowlisted `return_to`; `no-store` |
| `GET /auth/callback` | Unauthenticated callback transaction | Строгая OIDC validation; existing active identity получает обычную session, invitation path — только pending enrollment и ограниченную session без membership; неизвестный user без invitation отклоняется; `no-store` |
| `GET /auth/session` | Limited or authenticated session | Минимальный pending/user/tenant/roles state + CSRF token; `no-store` |
| `POST /auth/invitations/accept` | Session-bound pending enrollment | CSRF + Origin + повторная проверка invitation/identity; атомарно активировать membership и ротировать session token |
| `POST /auth/logout` | Limited or authenticated session | CSRF; revoke current session |
| `POST /auth/logout-all` | Authenticated + recent auth | CSRF; revoke all user sessions |
| `POST /api/v1/admin/invitations` | PA | Recent MFA, exact tenant/role/expiry, audit |
| `POST /api/v1/admin/users/{id}/suspend` | PA | Recent MFA, reason, revoke sessions, audit |
| `POST /api/v1/channels/telegram/link` | T + recent auth | Создать short-lived one-time link intent token digest |
| `POST /api/v1/channels/telegram/link/confirm` | T + recent auth | CSRF; подтвердить показанный PWA pending Telegram account и только тогда создать active link |
| `DELETE /api/v1/channels/telegram/link` | T + recent auth | Revoke mapping немедленно |
| `POST /internal/telegram/link/redeem` | S(`telegram.link.redeem`) | Atomic single-use transport token; private chat; создать только `pending_confirmation`, не active link; internal ingress |

OIDC callback не выражает согласие вступить в tenant, а Telegram redeem не доказывает владение web-аккаунтом. Оба потока активируются только отдельным явным PWA confirmation с текущей session и CSRF.

## 6. Resource policy, а не только role check

`teacher` недостаточно проверить одной строкой. Для каждого object endpoint policy должна доказать:

1. resource существует в effective tenant;
2. resource опубликован global либо tenant-private;
3. пользователь владелец или имеет явный share/membership permission;
4. parent IDs принадлежат тому же tenant;
5. статус допускает операцию (`published`, `quality_passed`, `ready` и т. п.);
6. channel/service scope допускает действие от имени effective user;
7. quota, recent-auth и support-grant требования выполнены.

Проверка делается до получения/возврата чувствительных metadata. UUID не считается секретом.

## 7. PWA, browser cache и персональные данные

В пилоте offline-доступ к персональным данным отключён. Service worker может cache-ировать только versioned static assets, одинаковые для всех пользователей.

- `/api/v1/**`, `/auth/**`, export/download route-ы, tenant-specific HTML и ответы с `Set-Cookie` используют network-only и не попадают в Cache Storage.
- Персональные/session responses возвращают `Cache-Control: private, no-store`; при наличии промежуточных proxy дополнительно задаётся корректный `Vary: Cookie, Authorization`.
- Prompts, plans, source snippets, class context, feedback, runs, filenames и документы не сохраняются PWA в `localStorage`, IndexedDB, Cache Storage или background sync queue.
- Явно скачанный пользователем DOCX/PDF является пользовательским файлом вне PWA cache; приложение не создаёт его скрытую offline-копию.
- Logout, logout-all, tenant switch, session revoke и вход другого пользователя очищают in-memory персональное состояние; после back/forward navigation session перепроверяется до показа данных.
- Offline PWA показывает только обезличенный shell и сообщение о необходимости подключения, но не последний персональный экран или документ.

## 8. Обязательный audit по операциям

| Категория | События |
|---|---|
| Identity | login success/failure, logout, revoke, invitation, role/membership change |
| Channels | Telegram link/redeem/unlink, service credential rotate/revoke |
| Library | upload, ingest, embed, review, publish, withdraw, raw page access |
| Teacher data | generation, external web call, export create/download/delete |
| Privileged | feedback read, stats, support grant/use/revoke, quota override |
| Deny | Повторяющиеся/чувствительные authorization denials и cross-tenant attempts |

Audit не содержит raw token, cookie, secret, полный prompt/учебник или DOCX/PDF.

## 9. Проверка полноты матрицы

CI должен получить список FastAPI routes и сравнить его с policy registry. Тест падает, если:

- появился route без policy ID;
- state-changing browser route не требует CSRF;
- object route не объявил resource loader/tenant policy;
- expensive route не объявил quota/cost policy;
- public route возвращает больше разрешённой минимальной схемы;
- unauthenticated route не классифицирован явно как `health` либо `auth_bootstrap`;
- service route допускает credential с неверным `audience` или scope;
- personalized route допускает browser/service-worker/shared-proxy cache.

Параметрические role × route и cross-tenant тесты перечислены в [`IDENTITY_TENANCY_ACCEPTANCE.md`](IDENTITY_TENANCY_ACCEPTANCE.md).
