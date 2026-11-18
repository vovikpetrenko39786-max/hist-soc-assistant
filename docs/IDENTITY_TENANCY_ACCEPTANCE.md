# Критерии приёмки identity, RBAC и tenant isolation

**Статус:** blocking gate для закрытого пилота
**Дата:** 2026-11-18
**Scope:** web/PWA, API, PostgreSQL/RLS, Telegram, storage, workers и operations

## 1. Правило прохождения gate

Закрытый пилот с 3–4 преподавателями разрешён только если:

- все обязательные automated tests проходят на PostgreSQL/pgvector той же major-версии, что staging;
- cross-tenant, RLS, pool и storage negative tests для включённого pilot scope не помечены `skip`/`xfail`; отложенная private-source функция имеет отдельный тест fail-closed/disabled, а полный suite становится blocking до её включения;
- ручные/операционные проверки имеют датированные evidence и ответственного;
- route inventory не содержит endpoint без policy;
- staging rehearsal выполнен на синтетических данных либо восстановленной обезличенной копии;
- production не использовался как тестовый стенд;
- владелец письменно принимает перечисленные остаточные риски.

Наличие happy-path login или UI не компенсирует провал любого blocking security test.

## 2. Обозначения и тестовый набор

- **A** — автоматизированный test в CI.
- **I** — integration test с реальным PostgreSQL/filesystem/provider stub.
- **M** — ручная проверка с evidence.
- **O** — операционная проверка/репетиция.

Минимальные identities:

| Principal | Tenant | Роли/scopes |
|---|---|---|
| `teacher_a` | A personal | `teacher` |
| `teacher_b` | B personal | `teacher` |
| `tenant_admin_a` | A | `tenant_admin`; future-ready negative principal, без доступа к teacher content в пилоте |
| `editor` | none | `content_editor` |
| `platform_admin` | none | `platform_admin` |
| `support_for_a` | A | PA + active scoped grant |
| `telegram_gateway` | none | `telegram.link.redeem`, `assistant.preview_for_linked_user`, `assistant.invoke_for_linked_user`, `feedback.create_for_linked_user`, `exports.download_for_linked_user` |
| `generation_worker` | none | `generation.run`, `retrieval.search`, `web.search`, `web.policy.read`, `outputs.render` |
| `library_worker` | none | `sources.import`, `sources.ingest`, `sources.status.read`, `sources.read_raw`, `sources.embed` |
| `internal_monitor` | none | `operations.readiness` |
| anonymous/invalid/revoked | none | none |

Для A и B создаются одинаковые по форме, но разные resource ID: class group, class course, lesson, progress, homework, generation run, export, web search и feedback. Global catalog содержит published и draft записи. Tenant-private source fixtures добавляются только в условный suite после включения соответствующей функции.

### 2.1. Зафиксированные допущения пилота

- Первичный enrollment доступен только 3–4 приглашённым совершеннолетним преподавателям; существующий active user повторно входит через OIDC без нового invitation. Student accounts и student PII не создаются.
- У каждого преподавателя отдельный personal tenant и одна активная membership. School tenant, tenant switch, sharing и совместное владение отключены, хотя future-ready schema/tests могут моделировать их отдельно.
- `tenant_admin_a` используется для отрицательных RBAC-тестов и не получает доступ к содержимому `teacher_a` только из-за роли.
- Teacher работает с curated global library. Teacher upload и tenant-private source publication отложены; private-source tests выполняются как отдельный условный suite только после feature flag и соответствующей migration/policy.
- PWA — same-origin BFF с cookie session; персональный offline mode отсутствует.
- Telegram доступен только linked invited user через отдельный gateway credential и обязательное PWA confirmation.
- Platform admin не имеет private-data bypass без active support grant.
- Это целевые условия gate, а не описание возможностей текущего `main` или production.

## 3. Public surface и fail-closed routing

### ID-AUTH-001 — public application surface и auth bootstrap (A)

**Когда:** anonymous вызывает все зарегистрированные routes.
**Тогда:**

- `GET /health` возвращает только минимальный status и является единственным anonymous application/operational endpoint;
- каждый текущий `/api/v1/**` возвращает `401`;
- будущие `/auth/login` и `/auth/callback` доступны только как invitation enrollment либо existing-user login bootstrap transaction, не возвращают product data и имеют `Cache-Control: no-store`;
- `/auth/session`, invitation acceptance, logout и channel/admin routes без допустимой limited/full session возвращают `401`;
- internal readiness недоступен через public ingress и не раскрывает provider/model/secret flags;
- `/openapi.json`, `/docs`, `/docs/oauth2-redirect` и `/redoc` в production отключены либо защищены отдельной policy; они не считаются auth bootstrap.

### ID-AUTH-002 — route policy inventory (A)

CI извлекает method/path из FastAPI и сравнивает с policy registry. Build падает, если route:

- не имеет policy ID;
- mutation с browser session не объявляет CSRF;
- object route не объявляет resource/tenant policy;
- expensive route не объявляет quota/cost policy;
- public route не входит в явный allowlist.

Текущий baseline: ровно 35 `/api/v1` операций — `router` 1, `class-courses` 1, `lessons` 2, `catalog` 4, `exams` 5, `sources` 5, `retrieval` 2, `generation` 1, `pedagogy` 1, `outputs` 4, `assistant` 2, `pilot` 4, `admin/library` 1 и `web` 2. Отдельно объявлен `GET /health`. Они подключены в [`app/main.py`](../app/main.py#L25-L42), а общей auth dependency пока нет. Будущие auth/channel route-ы из matrix в число 35 не входят до регистрации в FastAPI.

### ID-AUTH-003 — единообразные ответы (A)

- нет/невалидный/expired/revoked credential → `401`;
- подходящая identity, но запрещённая роль/scope → `403`;
- неизвестный и чужой tenant-resource внешне дают одинаковый `404`;
- ответ не содержит stack trace, SQL, path, provider response или secret.

### ID-AUTH-004 — limited bootstrap session (A/I)

- OIDC callback создаёт только pending enrollment и ограниченную server-side session без active membership и доступа к `/api/v1`;
- limited session разрешает только просмотр минимального enrollment state, accept и logout;
- `POST /auth/invitations/accept` требует ту же session, synchronizer CSRF, допустимый `Origin` и повторную проверку invitation/identity;
- успешный accept атомарно погашает invitation, активирует membership и ротирует session token;
- callback, refresh страницы, back navigation и replay invitation сами по себе не активируют membership.

Ограниченная session относится только к первичному/pending enrollment. Для уже известной active `(issuer, subject)` callback после полной OIDC validation создаёт обычную session без требования нового invitation; suspended user/membership остаётся заблокирован.

## 4. OIDC и приглашения

### ID-OIDC-001 — успешный invite-only flow (A/I)

Валидные invitation, state, nonce, PKCE S256, issuer, audience, signature и code после callback создают ровно одну `(issuer, subject)` identity, pending user/enrollment и ограниченную server session, но **не** active membership. PWA показывает точные tenant/account/role из server-side invitation. Только отдельный `POST /auth/invitations/accept` из той же session, с CSRF, допустимым `Origin` и повторной проверкой invitation/identity, атомарно погашает invitation, создаёт либо активирует membership и ротирует session token. Повтор callback или accept не создаёт дубликат и не активирует membership повторно.

### ID-OIDC-001R — повторный вход active user (A/I)

Уже существующая active `(issuer, subject)` с active user/membership начинает обычную login transaction без нового invitation. После полной проверки state, nonce, PKCE, issuer, audience, signature и времени callback создаёт обычную server session, не создавая новый `User`, identity, membership или enrollment. Неизвестный subject без invitation и suspended/disabled user либо membership session не получают.

### ID-OIDC-002 — protocol negative matrix (A)

Каждый сценарий отклоняется без session:

- отсутствующий, чужой, истёкший или replayed `state`;
- неверный `nonce` или `code_verifier`;
- повторно использованный authorization code/login transaction;
- неверные `issuer`, `audience`, `azp`, signature или запрещённый algorithm;
- истёкший/слишком ранний token;
- JWKS failure/unknown key без принятия непроверенного token;
- redirect/`return_to` вне allowlist;
- неизвестный user/subject без invitation при отключённом self-signup; существующий active user проверяется отдельным returning-login сценарием;
- suspended/disabled user, tenant или membership.

Ни один отрицательный callback не создаёт active membership. Пересланная invitation, совпадение только домена/display name, callback без явного PWA accept и accept из другой session/с неверным CSRF также отклоняются.

### ID-OIDC-003 — стабильная identity (A)

- изменение email у той же `(iss, sub)` не создаёт нового user;
- одинаковый email у другого `(iss, sub)` не объединяет аккаунты;
- unverified email не погашает invitation, если verified email обязателен;
- provider token/code/PKCE verifier не появляется в API response, log или audit.

### ID-OIDC-004 — privileged MFA/recent auth (A/M)

Platform role требует подтверждённой MFA claim/policy выбранного IdP. Role change, support grant, service credential rotation и sensitive user suspension требуют недавней аутентификации согласно утверждённому TTL.

## 5. Web sessions

### ID-SES-001 — cookie (A)

Session cookie имеет `__Host-` prefix, `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, без `Domain`; token отсутствует в URL, HTML, JavaScript-readable storage и response body.

### ID-SES-002 — хранение и rotation (A/I)

- session secret не менее 256 бит;
- в БД только digest/HMAC, raw secret не найден запросом/лог-сканом;
- после login, reauthentication, tenant switch и повышения привилегий token меняется;
- старый token после rotation не работает;
- concurrent rotation не оставляет две непредусмотренные активные sessions.

### ID-SES-003 — expiry/revoke (A/I)

Проверяются idle и absolute timeout. Logout отзывает текущую session, logout-all — все user sessions. Disable user/membership, role change/authz version increment и incident revoke прекращают доступ на следующем запросе.

### ID-SES-004 — отказ session store (I)

При недоступном session store protected API fail closed и не создаёт анонимный/кэшированный principal. IdP outage блокирует новый login, но не расширяет срок уже валидной локальной session.

### ID-SES-005 — окружения (A/M)

Dev/staging/production cookies имеют непересекающиеся host/scope/name настройки. Staging cookie не принимается production и наоборот.

## 6. CSRF, CORS и browser safety

### ID-CSRF-001 — mutation matrix (A)

Для каждого cookie-authenticated `POST/PUT/PATCH/DELETE`:

- отсутствующий, неверный, expired или принадлежащий другой session CSRF token → `403`;
- чужой/отсутствующий при обязательности `Origin`/`Referer` → `403`;
- корректные session + CSRF + origin проходят до authorization policy;
- простой cross-site form content type не обходит защиту.

Минимум покрываются invitation accept, logout/logout-all, lessons, feedback, assistant, admin actions, CE-операции ingestion/embedding и Telegram link create/confirm/unlink. Service-only generation, retrieval, render и web route-ы не полагаются на CSRF: browser cookie principal и browser CORS на них отклоняются, а machine credential проверяется отдельно.

### ID-CSRF-002 — safe methods/CORS (A/M)

- `GET/HEAD/OPTIONS` не меняют данные;
- CORS не сочетает wildcard origin с credentials;
- preflight разрешает только нужные origin/method/header;
- персональные responses имеют `Cache-Control: no-store`;
- CSP и escaping не допускают исполнения raw user/LLM HTML в PWA.

## 6.1. PWA cache isolation

### ID-CACHE-001 — headers и shared cache (A/I)

- `/api/v1/**`, `/auth/**`, authenticated navigation, export/download и responses с `Set-Cookie` возвращают `Cache-Control: private, no-store`; bootstrap/health используют как минимум `no-store`;
- authenticated responses задают корректный `Vary: Cookie, Authorization` там, где возможен proxy/CDN;
- CDN/reverse proxy не сохраняет body, redirect, filename или metadata персонального ответа;
- signed/download URL, если появится, не отменяет `no-store` и owner authorization.

### ID-CACHE-002 — service worker strategy (A/I)

- Service worker использует network-only для `/api/v1/**`, `/auth/**`, outputs/downloads, tenant-specific HTML и любого запроса с credentials;
- Cache Storage содержит только versioned static app shell/assets, одинаковые для всех пользователей;
- `cache.put`, runtime caching и background sync не сохраняют prompt, plan, lesson, class context, source snippet, feedback, run/export metadata или документ;
- offline request к персональному route не получает stale response и показывает только обезличенный shell/сообщение о необходимости подключения.

### ID-CACHE-003 — browser storage и смена пользователя (A/I)

- Session/CSRF token, identity, prompt, lesson, feedback, filenames и документы отсутствуют в `localStorage`, IndexedDB и Cache Storage;
- после logout, logout-all, session revoke и tenant switch очищается in-memory user state и любые user-scoped stores;
- сценарий `teacher_a → logout/revoke → teacher_b` в одном browser profile не показывает данные A через offline mode, back/forward cache, history restore или stale service worker;
- возврат по Back/Forward и `pageshow` перепроверяет session до рендера персонального экрана.

### ID-CACHE-004 — explicit downloads (A/M)

Явно сохранённый пользователем DOCX/PDF считается пользовательским файлом вне PWA cache. PWA не создаёт скрытую offline-копию, preview cache или повторно доступный object URL после logout; shared-device guidance проверена вручную.

## 7. RBAC и service scopes

### ID-RBAC-001 — role × route matrix (A)

Параметрический тест реализует каждую строку [`AUTHORIZATION_MATRIX.md`](AUTHORIZATION_MATRIX.md): положительный principal проходит, остальные получают `403`/`404`. Route с policy `Disabled` возвращает `404` всем; временный diagnostic service-доступ тестируется только при явном non-production flag. Роли не иерархические.

### ID-RBAC-002 — teacher (A/I)

Teacher управляет только разрешёнными данными своего tenant-а, создаёт generation/export/feedback и читает только published global catalog. Teacher не может ingest, embed, publish, получить raw source page/draft или управлять users/roles.

### ID-RBAC-003 — content editor (A/I)

CE управляет review/ingestion/embedding/publish global library, но не читает private class, prompt, generation output, export или feedback другого tenant-а без отдельной продуктовой причины/grant.

### ID-RBAC-004 — platform admin/support (A/I)

PA управляет invitations, users, roles, revoke, quotas и operational aggregates, но не получает постоянный private-data bypass. Доступ к tenant A работает только с active support grant на A, нужным scope, reason и TTL; tenant B остаётся недоступен.

### ID-RBAC-005 — service principals (A/I)

- Telegram gateway принимает только `telegram.link.redeem`, `assistant.preview_for_linked_user`, `assistant.invoke_for_linked_user`, `feedback.create_for_linked_user`, `exports.download_for_linked_user`; он не может ingest/embed/admin/publish и не выбирает произвольный effective user.
- Generation worker принимает только `generation.run`, `retrieval.search`, `web.search`, `web.policy.read`, `outputs.render`; он не управляет users/roles/library publication.
- Library worker принимает только `sources.import`, `sources.ingest`, `sources.status.read`, `sources.read_raw`, `sources.embed`; он не читает private teacher runs/exports и не публикует source без отдельного human review.
- Internal monitor принимает только `operations.readiness` и не получает product data.
- Credential каждого workload имеет отдельный audience; объединённый «service super-token» отсутствует.
- Worker job server-bound к tenant/effective user/resource IDs; подмена этих IDs в payload не расширяет job capability.
- Service-only route отклоняет browser cookie principal/CORS и недоступен с public ingress, если это допускает deployment topology.
- revoked/expired/wrong-audience credential → `401`.
- scope escalation через payload/header невозможен.

### ID-RBAC-006 — shared keys (A/M)

`X-Admin-Key`, pilot key, `X-User-ID`, `X-Tenant-ID` и `client_context` не считаются human identity. После cutover старый key не открывает protected endpoints.

## 8. Cross-tenant HTTP/IDOR

Для каждого private type тестируются create/read/list/update/delete, если операция существует, а также parent references и aggregate counts.

### ID-TEN-001 — resource matrix (A/I)

Обязательные типы:

- `teacher_profiles`, `class_groups`, `class_courses`;
- `lessons`, `curriculum_progress`, `homework`;
- `generated_materials`, `generation_runs`;
- `exported_files`, `web_search_runs`, `pilot_feedback`;
- tenant-private sources/pages/chunks/revisions — только в условном suite после отдельного feature rollout;
- будущие conversations/messages/jobs/user settings.

Teacher A не читает, не изменяет, не удаляет, не перечисляет и не считает B resource даже при известном UUID.

### ID-TEN-002 — cross-parent creation (A/I)

A не может создать child, указав `class_course_id`, `lesson_id`, `generation_run_id` или иной parent B. Cross-tenant `source_id` добавляется в этот blocking test одновременно с private-source feature. DB composite FK также отвергает такую запись при прямой попытке под app role.

### ID-TEN-003 — caller-supplied ownership (A)

Переданные `tenant_id`, `teacher_id`, `owner_user_id`, `user_id`, `user_external_id`, role либо игнорируются и заменяются principal, либо schema отклоняет их. Response подтверждает server-derived owner.

### ID-TEN-004 — особо опасные endpoint-ы (A/I)

Отдельные A/B cases обязательны для:

- `/class-courses/{id}/context` со всеми вложенными rows;
- `/lessons/{id}/complete`;
- `/outputs/files/{export_id}`;
- `/outputs/runs/{run_id}`;
- `/pilot/feedback` с чужим run ID;
- `/sources/{id}/pages/{page}` — в пилоте оба teacher получают отказ на raw page; A/B ownership case добавляется с private-source feature;
- `/assistant` с поддельным `client_context`;
- source/status/archive filters, которые пытаются расширить server scope.

## 9. PostgreSQL constraints и RLS

Tests выполняются под реальной low-privilege runtime role, не migration owner.

### ID-RLS-001 — direct SQL isolation (I)

Под tenant A `SELECT/INSERT/UPDATE/DELETE` B rows не возвращают/не изменяют данные. `WITH CHECK` блокирует подстановку B tenant. Tests проверяют row counts и фактические persisted rows.

### ID-RLS-002 — fail closed (I)

При отсутствующих/пустых/invalid `app.tenant_id` и `app.user_id` private query не возвращает строки либо даёт контролируемую ошибку. Предыдущий tenant context не является default.

### ID-RLS-003 — roles и bypass (I/O)

- runtime role: `NOSUPERUSER`, `NOBYPASSRLS`, не owner private tables;
- private tables: `ENABLE` + `FORCE ROW LEVEL SECURITY`;
- migration role отделён и не используется runtime secret;
- service role не имеет общего bypass и использует documented policy/scope.

### ID-RLS-004 — composite FK (I)

Для каждого tenant parent/child `(tenant_id, parent_id)` отвергает cross-tenant reference. Все constraints валидированы; нет `NULL tenant_id`, orphan и conflict rows после backfill.

### ID-RLS-005 — global source policy и условный private-source rollout (I)

Обязательный пилотный тест: teacher читает только published global sources, но не global draft/withdrawn; CE меняет global editorial rows без доступа к private teacher data. Проверки own/B-private, global row с tenant ID и private row без него остаются blocking, но запускаются только после отдельного включения private-source feature, migration, revision model и policy. До этого teacher upload/private publication отсутствуют и fail closed.

## 10. Connection pool isolation

### ID-POOL-001 — последовательное reuse (I)

На одной физической connection выполняются не менее 100 чередований A/B/anonymous. B ни разу не видит A; anonymous после authenticated transaction не наследует tenant.

### ID-POOL-002 — abnormal termination (I)

После exception, rollback, timeout, task cancellation, client disconnect и failed commit следующий borrower не наследует context. `SET LOCAL` действует только внутри transaction.

### ID-POOL-003 — concurrency (I)

Параллельные запросы A/B и одного user с разными memberships не смешивают context/result. Background task не использует request session после закрытия.

## 11. Telegram linking и delegated access

### ID-TG-001 — unlinked/spoofed user (A/I)

Unlinked Telegram user не вызывает assistant, feedback или download. Прямой HTTP-клиент с копией `client_context`, `telegram_user_id`, username/chat ID не получает principal.

### ID-TG-002 — linking token (A/I)

Token случаен, хранится только digest, TTL не более 10 минут и погашается gateway атомарно один раз только в direct private chat. Redeem фиксирует наблюдаемый `(bot_id, telegram_user_id)` и переводит intent лишь в `pending_confirmation`; active link ещё не создаётся. PWA показывает точный pending Telegram account, а отдельный confirm требует исходного web user, recent-auth session, CSRF и допустимый `Origin`. Только confirm атомарно создаёт active link. Expired, replayed, revoked, altered token, group/channel/forum redeem, confirm из другой session и token, использованный повторно/другим account, отклоняются; неподтверждённый intent истекает без доступа.

### ID-TG-003 — service credential (A/I)

Redeem принимает только gateway с `telegram.link.redeem`. Preview/assistant/download/feedback требуют соответственно `assistant.preview_for_linked_user`, `assistant.invoke_for_linked_user`, `exports.download_for_linked_user`, `feedback.create_for_linked_user` и active server-side mapping. Bot token не принимается как backend credential.

### ID-TG-004 — unlink/revoke (A/I)

Web unlink, user/membership disable и Telegram link revoke блокируют следующий bot request. Повторная привязка требует active web session и recent auth.

### ID-TG-005 — delegated audit (A/I)

Audit фиксирует service actor, effective user, tenant, action, target и outcome, не сохраняя link/session/service secret.

## 12. Source ingestion и content safety

### ID-SRC-001 — file limits/quarantine (I)

Fake extension, неверные magic bytes/MIME, oversized file, high page count, encrypted/corrupt PDF и zip/polyglot-like inputs отклоняются до publication. Temp/quarantine data очищается согласно policy.

### ID-SRC-002 — atomic revision (I)

Parser crash, timeout, disk-full, DB error и embedding failure не изменяют ранее published revision/pages/chunks. Новая revision становится active только после полного validation/review/publish.

### ID-SRC-003 — sandbox (I/O)

Parser/converter worker работает non-root, без лишнего network egress, с CPU/RAM/pids/time/disk limits. Malicious input не читает host paths и не оставляет бесконтрольный subprocess.

### ID-SRC-004 — prompt injection/provenance (A/I)

Corpus с инструкциями «игнорируй правила», поддельными citations и попытками получить чужой контекст:

- не меняет principal/roles/source scope/tool allowlist;
- не извлекает B content;
- не публикует source;
- не создаёт citation без server-side source reference;
- приводит к warning/quality failure при неподтверждённых утверждениях.

## 13. Outputs и storage

### ID-OUT-001 — authorize before metadata/file (A/I)

Запрос A к B export не раскрывает имя, size, checksum, status, path или существование. Authorization выполняется до DB metadata response и filesystem/object read.

### ID-OUT-002 — path/object integrity (I)

Проверяются `../`, absolute path, symlink/hardlink где применимо, case/encoding variants, DB path вне root, TOCTOU, missing file, size mismatch и SHA-256 mismatch. Все fail closed.

### ID-OUT-003 — namespace/lifecycle (I)

Object key содержит tenant namespace и opaque ID, а не пользовательское имя. Revoked/deleted/quality-failed export не скачивается. Signed URL, если используется, имеет short TTL, exact object/audience и не расширяет права.

### ID-OUT-004 — Telegram temp files (A/I)

Temp file удаляется при success, send failure, timeout и cancellation. Filename/content одного tenant не переиспользуется другим.

## 14. Rate limits, стоимость и idempotency

### ID-COST-001 — layered limits (A/I)

`/assistant`, generation, web search, render, ingestion и embedding имеют user, tenant, IP/channel и global concurrency/daily limits. Превышение возвращает `429` + `Retry-After` до внешнего вызова.

### ID-COST-002 — race/idempotency (I)

Параллельные запросы не обходят quota. Повтор с тем же idempotency key не создаёт второй run/export/job и не списывает бюджет повторно.

### ID-COST-003 — policy cannot expand (A/I)

Поля payload (`allow_web_fallback`, web scope, formats, artifacts, force/retry и подобные) могут только сузить server policy и не расширяют tenant/user budget или service scope. Anonymous/denied request не вызывает OpenAI, embeddings, LibreOffice/PDF или source parser.

### ID-COST-004 — metrics/audit (I/M)

Usage привязан к tenant/user/operation/correlation ID, но prompt/PII не используется как metric label. Admin override требует reason, recent auth и audit.

## 15. Audit и support access

### ID-AUD-001 — покрытие (A/I)

Audit создаётся для login failure/success, logout/revoke, invitation, membership/role, Telegram link/unlink, service credential, source ingest/review/publish, generation/web, export/download, support grant/use/revoke и quota override.

### ID-AUD-002 — минимизация и неизменяемость (I/O)

Событие содержит actor/effective user/tenant/action/target/outcome/request ID/time и очищенные metadata. Cookie, token, DB URL, secret, полный prompt, учебник и generated document отсутствуют. Обычная app role не обновляет/удаляет audit.

### ID-AUD-003 — support grant (A/I)

Grant имеет target tenant, reason, exact scopes, issuer, TTL и revoke. Every use аудитируется. Expired/revoked grant немедленно не работает; grant A не открывает B.

## 16. Privacy, logs и retention

### ID-PRIV-001 — automated leak scan (A/I)

HTTP errors, logs, traces, audit и CI artifacts сканируются на session/OIDC/link/service tokens, bot/OpenAI/DB credentials, полный private prompt и filesystem paths. Test fixtures используют только synthetic secrets.

### ID-PRIV-002 — provider minimization (M/O)

Документированы данные для каждого provider, region/retention/training settings, DPA/договорное основание и deletion procedure. Student names/identifiers не отправляются и не собираются в пилоте.

### ID-PRIV-003 — lifecycle (A/O)

Утверждены сроки для sessions, login/link tokens, prompts/runs, feedback, exports, logs, audit и backups; retention private sources добавляется до включения соответствующей функции. Cleanup job идемпотентен, scoped по tenant и имеет dry-run/report; legal hold описан отдельно.

## 17. Backup, restore и эксплуатация

### ID-OPS-001 — restore rehearsal (O)

Backup восстанавливается в отдельное окружение. После restore автоматически проверяются schema revision, row counts/checksums, composite constraints, RLS policies, DB roles, tenant A/B isolation, storage references и audit continuity.

### ID-OPS-002 — secret rotation/revoke (O)

Репетиция подтверждает rotation OIDC client secret, bot token, service credential, provider key и DB credential без раскрытия значений. Старые credentials немедленно или в утверждённое overlap window перестают работать.

### ID-OPS-003 — dependency/container gate (A/O)

- runtime запускается non-root;
- dependencies зафиксированы воспроизводимо с hashes/lock;
- SBOM и container/dependency scan не имеют непринятых critical findings;
- filesystem/egress/resource limits соответствуют threat model.

### ID-OPS-004 — observability/incident (M/O)

Есть alerts для auth failures, cross-tenant denies, provider cost anomaly, ingestion failure, disk/storage, session-store/DB outage и audit pipeline failure. Указаны ответственный, канал инцидента, revoke/containment steps и recovery evidence.

## 18. Рекомендуемые test suites

| Файл | Назначение |
|---|---|
| `tests/security/test_auth_public_surface.py` | Public allowlist, policy inventory, response semantics |
| `tests/security/test_oidc_flow.py` | OIDC/invitation/replay/claims |
| `tests/security/test_sessions_csrf.py` | Cookie lifecycle, revoke, CSRF/CORS |
| `tests/security/test_pwa_cache_isolation.py` | Headers, service worker, offline fail-closed, A→logout→B cache regression |
| `tests/security/test_authorization_matrix.py` | Параметрическая role × route |
| `tests/security/test_tenant_idor.py` | HTTP A/B resource matrix |
| `tests/security/test_rls_postgres.py` | Direct SQL RLS/composite FK |
| `tests/security/test_pool_context_isolation.py` | Reuse/rollback/cancel/concurrency |
| `tests/security/test_telegram_linking.py` | Linking, spoof/replay, delegation scopes |
| `tests/security/test_source_ingestion_security.py` | Limits, sandbox, atomic revision |
| `tests/security/test_export_authorization.py` | Storage/path/checksum/download |
| `tests/security/test_rate_limits.py` | Quota, concurrency, idempotency |
| `tests/security/test_audit_support_access.py` | Audit completeness/immutability/grants |
| `tests/security/test_prompt_injection_boundaries.py` | Auth/tool/provenance invariants |

Это предлагаемые имена; файлов пока нет. Текущий test suite не содержит OIDC/session/CSRF/RBAC/RLS/tenant tests.

## 19. Формат evidence и итоговое решение

Для каждого test/gate сохраняются:

- commit SHA, migration revision, image digest;
- PostgreSQL/pgvector/runtime versions;
- synthetic fixture version;
- команда/CI run URL и полный result summary;
- skips/known deviations (для blocking tests допустимо ноль);
- оператор, дата, среда и ссылка на redacted artifact;
- остаточный риск, владелец риска и срок устранения.

Итоговый pilot sign-off подписывают владелец продукта и технический ответственный. Он не разрешает merge/deploy автоматически: deployment остаётся отдельным change с rollback plan.
