# Дорожная карта развития Hist-Soc Assistant

**Горизонт документа:** от завершения аудита до закрытого пилота с 3–4 преподавателями  
**Подход:** короткие проверяемые этапы; каждый этап завершается решением go/no-go  
**Важно:** оценки — ориентиры после уточнения команды и production inventory, а не обязательство по календарной дате.

## 1. Принципы поставки

1. Production не используется для экспериментов.
2. Сначала сохранность, identity и изоляция; затем новые продуктовые функции.
3. Миграция данных всегда имеет backup evidence, rehearsal и проверяемый backfill report.
4. Учебный корпус вводится узкими утверждёнными ревизиями.
5. Технический pass не заменяет методическую приёмку.
6. Один PR решает одну обозримую проблему; PR №8 не объединяется автоматически целиком.
7. Каждый этап содержит документацию, тесты, rollback/roll-forward и список непроверенного.
8. Пилот не начинается с известным P0.

## 2. Потоки работ

| Поток | Результат к пилоту |
|---|---|
| Platform | воспроизводимые сборки, CI, migrations, backups, staging |
| Identity & tenancy | персональный вход, роли, RLS, zero cross-tenant access |
| Content | утверждённая ограниченная библиотека с revision/rights/coverage |
| Intelligence | conversational plan, strict source, evidence, multi-stage generation |
| Quality | golden set, deterministic + factual + method gates, human approval |
| Documents | immutable teacher/student DOCX/PDF и безопасная выдача |
| Experience | PWA и связанный Telegram channel |
| Operations | jobs, monitoring, budgets, incident/restore runbooks |

## 3. Этап 0 — утверждение аудита и решений

**Ориентир:** 2–4 рабочих дня после получения документов.

### Работы

- владелец утверждает/корректирует [PROJECT_VISION.md](PROJECT_VISION.md) и [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md);
- triage P0/P1 из [TECHNICAL_AUDIT.md](TECHNICAL_AUDIT.md);
- read-only inventory Railway, GitHub, DB, storage и providers;
- выбор владельцев решений: технический, предметный, методический, privacy;
- ADR для identity, tenancy, migrations, queue, object storage и PWA;
- решение по разбиению PR №8.

### Артефакты

- утверждённый scope пилота;
- risk register с owner/date/status;
- environment/data-flow diagram;
- список corpus revision 1;
- backlog с dependency order.

### Exit gate

- нет неизвестного владельца у P0;
- production inventory получен без секретов;
- agreed source/pilot scope не обещает отсутствующее покрытие;
- определено, какие изменения PR №8 переносятся отдельными PR.

## 4. Этап 1 — безопасный инженерный baseline

**Ориентир:** 1 неделя.

### Работы

- lock dependencies и закрепить runtime/tool versions;
- CI: unit/integration, Ruff correctness baseline, secret/dependency/image scan;
- перенести из PR №8 schema/release smoke, readiness и безопасные output integrity checks после review;
- подготовить staging, физически отделённый от production;
- внедрить Alembic baseline на точной копии схемы;
- формализовать backup/PITR/restore runbook;
- исправить P0 replacement ingest так, чтобы старая ревизия сохранялась;
- запретить выдачу/export `quality_failed`.

### Не входит

- массовая смена форматирования;
- новая генеративная функциональность;
- production migration до rehearsal и отдельного разрешения.

### Exit gate

- чистая БД поднимается только миграциями;
- upgrade с обезличенного snapshot проходит и даёт ожидаемые counts/indexes;
- restore drill проходит на отдельной БД с зафиксированным RPO/RTO;
- CI блокирует schema drift и новые correctness errors;
- failed ingest сохраняет active revision;
- production readiness fail-closed.

## 5. Этап 2 — identity, роли и tenant isolation

**Ориентир:** 1–2 недели.

### Работы

- OIDC/session integration по ADR;
- User/Identity/Tenant/Membership/Role schema;
- `tenant_id`/`owner_user_id` и composite FK для курсов, диалогов, runs, jobs, feedback, exports и web searches;
- legacy backfill с dry-run report;
- policy layer и role matrix для каждого route;
- RLS default-deny policies и transaction context;
- персональные audit events;
- invitation/block/delete flow;
- закрыть source ingest/embed/admin operations от teacher role;
- rate/concurrency/cost limits.

### Обязательные проверки

- два пользователя/два tenant: отрицательные API и direct SQL/RLS tests;
- попытки подменить UUID, user header, course ID, export ID;
- pool connection reuse не сохраняет tenant context;
- admin/content editor не получают лишнего доступа;
- backup → migration → backfill → rollback/roll-forward rehearsal.

### Exit gate

- 0 cross-tenant access во всей матрице [ACCEPTANCE_TESTS.md](ACCEPTANCE_TESTS.md);
- каждый `/api/v1` route имеет документированную policy;
- shared pilot key не используется как user identity PWA;
- все новые owner columns `NOT NULL` после проверенного backfill.

## 6. Этап 3 — versioned library, storage и jobs

**Ориентир:** 1–2 недели.

### Работы

- private object storage с immutable keys/checksums/signed URLs;
- SourceRevision, rights, review, activation/withdrawal;
- upload limits, file signature, quarantine/scan;
- job queue, worker, progress, cancellation, idempotency, retries/dead letter;
- перенос ingest/OCR/embed/LibreOffice из request path;
- extraction/coverage report;
- модель/размерность embeddings и index migration по ADR;
- transactional outbox и orphan cleanup;
- импорт небольшой corpus revision 1 только после прав/методической проверки.

### Exit gate

- повторная/параллельная загрузка не повреждает active revision;
- worker restart не теряет job и не создаёт дубликат;
- teacher не видит/не ищет private source другого teacher;
- approved corpus имеет 100% provenance/right/hash/revision metadata;
- retrieval benchmark на corpus revision 1 достигает согласованного порога;
- source и export восстанавливаются вместе с БД либо имеют документированную согласованность.

## 7. Этап 4 — assistant и course memory

**Ориентир:** 1–2 недели.

### Работы

- versioned Dialogue/Message/Interpretation/Plan;
- deterministic + structured semantic parser;
- short clarification state machine;
- tenant-scoped course context/preferences/progress;
- strict source и no-substitution policies;
- объединение тем и продолжение предыдущего занятия;
- explanation of interpreted request;
- prompt-injection boundaries и provider data policy.

### Exit gate

- golden NLU set проходит по intent/entities/constraints;
- неоднозначные запросы не запускают дорогую генерацию до ответа;
- «только учебник X» не использует иной источник;
- удалённая память перестаёт влиять на последующие requests;
- Telegram/PWA дают одинаковый server plan для одинакового principal/request.

## 8. Этап 5 — evidence и методический генератор

**Ориентир:** 2 недели.

### Работы

- query decomposition, curriculum mappings и paragraph coverage;
- immutable EvidenceSet и claim references;
- content map перед prose;
- три pilot-ready стратегии: lecture, combined, practical или иной утверждённый набор;
- lesson, worksheet, homework, small assessment;
- age/basic/advanced adaptations;
- keys/rubrics и проверка ответов;
- ограниченный revision loop при failed checks;
- ФИПИ/право freshness/status policy.

### Exit gate

- 45 минут точно суммируются; объём реалистичен по методической оценке;
- три сценария отличаются activity graph, а не заголовком;
- каждый обязательный content item имеет evidence либо явный gap;
- ни одна ссылка/страница/статус ФИПИ не выдуманы в golden set;
- задачи и ключи проходят independent verifier;
- failed quality не обозначается готовым.

## 9. Этап 6 — документы и PWA

**Ориентир:** 1–2 недели.

### Работы

- единый DocumentModel и preview;
- immutable export revisions;
- teacher/student DOCX/PDF, page numbering, tables, source notes;
- worker sandbox для LibreOffice и visual smoke;
- PWA: login, composer, clarification, progress, preview/evidence, courses, documents, settings;
- install manifest/service worker/offline shell;
- safe drafts; запрет неуправляемого cache private documents;
- accessibility/responsive testing.

### Exit gate

- document acceptance suite проходит на Windows Word и LibreOffice/PDF viewer;
- повторный export не меняет hash старой revision;
- signed URL чужого/истёкшего ресурса не работает;
- основные сценарии проходят на desktop/tablet/mobile;
- PWA устанавливается, offline корректно объясняет недоступность server generation.

## 10. Этап 7 — Telegram как дополнительный канал

**Ориентир:** 3–5 дней, параллельно после готовности identity/API.

### Работы

- one-time linking с web account;
- persistent dialogue/job state на backend;
- выбор только разрешённых курсов;
- одинаковые policy/limits/quality states;
- безопасная выдача документов;
- privacy/retention notice.

### Exit gate

- неподвязанный/заблокированный user не запускает generation;
- подмена Telegram/user header не меняет principal;
- restart bot не теряет серверный job/ownership;
- group chats запрещены или имеют отдельно утверждённую модель.

## 11. Этап 8 — закрытая техническая приёмка

**Ориентир:** 1 неделя.

### Работы

- полный acceptance suite;
- threat model review и targeted penetration tests;
- load/concurrency на профиль 4 преподавателей с запасом;
- provider outage, worker crash, low disk, DB reconnect, object storage errors;
- restore drill точной release candidate;
- cost envelope и alerts;
- incident, rollback, user support и data deletion drills;
- freeze corpus/model/prompt/application versions.

### Exit gate

- все P0/P1 pilot tests прошли;
- нет открытых critical/high security findings;
- restore выполнен и проверен по hashes/counts;
- runbooks выполнил человек, который их не писал;
- расходы укладываются в утверждённый бюджет;
- есть rollback к предыдущей release candidate.

## 12. Этап 9 — методическая приёмка владельцем

**Ориентир:** 1 неделя, зависит от объёма golden set.

### Работы

- владелец и методист оценивают эталонные сценарии вслепую по rubric;
- фактологические ошибки классифицируются и исправляются системно;
- измеряется объём ручной правки и реальная экономия времени;
- неудачные классы запросов выключаются feature flag, а не маскируются.

### Exit gate

- согласованный порог по достоверности, полноте, возрасту, методике и документам;
- 0 критических фактических ошибок в обязательном наборе;
- владелец подписывает corpus/eval/application release IDs;
- сформулированы известные ограничения для пилотных учителей.

## 13. Этап 10 — закрытый пилот 3–4 преподавателя

**Предлагаемая длительность:** 2 учебные недели.

### Перед стартом

- персональные приглашения и краткий onboarding;
- согласие/уведомление о данных и запрете загрузки лишних персональных данных учеников;
- назначенный канал поддержки и incident owner;
- feature flags только для прошедших сценариев;
- ежедневный мониторинг, backup и cost dashboard.

### Во время пилота

- собирать структурированную оценку материала, не только «понравилось»;
- фиксировать original request, interpretation, source revisions, quality report и объём правки по прозрачной политике;
- critical incident останавливает affected feature;
- не менять corpus/model/prompt без новой revision и smoke regression.

### Критерии успеха

- 0 cross-tenant/security/data-loss incidents;
- 0 материалов, ошибочно выданных как проверенные после failed gate;
- restore/backup/alerts продолжают работать;
- согласованный процент материалов полезен после небольших правок;
- учителя понимают evidence/ограничения и способны завершить основной сценарий без разработчика;
- средняя стоимость и latency находятся в утверждённом envelope;
- backlog после пилота классифицирован на blocker/important/later.

## 14. Обязательные gate перед пилотом

Пилот **не начинается**, если истинно хотя бы одно:

- пользовательская identity основана на общем ключе или подменяемом header;
- есть воспроизводимый cross-tenant доступ;
- migration/restore не репетировались;
- current source revision может быть уничтожена failed ingest;
- источник не имеет права использования/версии/hash;
- quality-failed результат можно скачать как готовый;
- ФИПИ `project` показывается как `final`;
- отсутствуют rate/cost limits или monitoring;
- DOCX/PDF нельзя связать с владельцем и exact generation/source revision;
- владелец не провёл методическую приёмку.

## 15. Что делать с PR №8

PR №8 не объединять целиком в `main` в рамках аудита. Предлагаемый backlog переноса:

1. **PR-A:** CI, schema/release smoke, readiness/preflight, без auth semantics.
2. **PR-B:** output integrity/storage/checksum/quality refusal с тестами.
3. **PR-C:** lesson schema/renderer/quality heuristics и golden documents.
4. **PR-D:** Telegram pilot UX только после новой identity/linking architecture.
5. **Не переносить напрямую:** shared-key + caller-supplied identity как основную PWA auth.

Каждый PR сверяется с head `e3fcb9b9c2df94f2f9f7f442a54f504d9455cca8`, чтобы не потерять полезные исправления и не импортировать временные ограничения незаметно.

## 16. Действия владельца по этапам

| Срок | Действие владельца |
|---|---|
| Сейчас | Утвердить scope, роли, pilot teachers, ADR owners, GitHub доступ |
| До этапа 1 | Дать production inventory, schema dump, backup/restore evidence |
| До этапа 3 | Дать файлы/метаданные/права и список первой corpus revision |
| До этапа 4 | Описать реальные курсы, разговорные запросы и memory preferences |
| До этапа 5 | Дать эталонные уроки/задания и назначить методиста |
| До этапа 6 | Утвердить шаблоны документов и поддерживаемые устройства/Word |
| До этапа 8 | Утвердить RPO/RTO, cost envelope, incident contacts |
| До пилота | Подписать release/corpus/eval version и известные ограничения |

## 17. После пилота

Только после отчёта пилота планируются расширение шести методик, полный экзаменационный модуль, карты/источники, совместный доступ, публичная регистрация, поддержка, публичный security review и монетизация. Платежи и массовый launch не входят в текущую дорожную карту.
