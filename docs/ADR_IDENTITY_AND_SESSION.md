# ADR: идентификация, сессии и доверенные каналы

**Статус:** предложено, требуется решение владельца до реализации\
**Дата:** 2026-11-18\
**Область:** web/PWA, API, Telegram, служебные процессы\
**Не является:** разрешением на изменение production, базы данных или секретов

## 1. Краткое решение

Технический аудит и общая дорожная карта опубликованы отдельно. Этот проект уточняет требования к входу и изоляции преподавателей для базы `main@a5235ce`. [Аудит и дорожная карта, PR №11](https://github.com/vovikpetrenko39786-max/hist-soc-assistant/pull/11).

Для закрытого пилота предлагается:

1. вход только по приглашению через внешний OpenID Connect (OIDC) provider;
2. поток Authorization Code с PKCE, `state` и `nonce`, завершаемый backend-ом;
3. непрозрачная серверная сессия в cookie `Secure`, `HttpOnly`, `SameSite=Lax`;
4. один персональный tenant на преподавателя в пилоте, но схема сразу допускает школьные tenant-ы с несколькими участниками;
5. авторизация по серверному `Principal`, сформированному из сессии и активного membership, а не из полей запроса;
6. роли `teacher`, `tenant_admin`, `content_editor`, `platform_admin` и отдельные service principals;
7. Telegram связывается с уже подтверждённой web-учётной записью одноразовым короткоживущим кодом; Telegram ID сам по себе не создаёт пользователя;
8. все изменяющие cookie-authenticated запросы защищаются CSRF-токеном и проверкой `Origin`;
9. пароли, OIDC access/refresh token и session token в открытом виде приложение не хранит.

OIDC как протокол является архитектурным предложением этого ADR, но конкретный provider
не выбран. Указанные далее TTL также являются кандидатами для closed pilot, а не
зафиксированными production-настройками. И provider, и TTL должен письменно утвердить
владелец; до этого контракт должен оставаться vendor-neutral и конфигурируемым.

## 2. Подтверждённое состояние `main`

Это факты, проверенные по исходному коду, а не описание желаемой системы.

- Все router-ы подключены под `/api/v1` без глобальной auth dependency в [`app/main.py`](../app/main.py#L25-L38).
- [`get_session()`](../app/api/deps.py#L8-L10) создаёт только SQLAlchemy session и не формирует пользователя, tenant или роли.
- Создание и завершение урока не проверяет владельца в [`app/api/routes/lessons.py`](../app/api/routes/lessons.py#L14-L54).
- Генерация, web-поиск и workflow вызываются без аутентификации в [`generation.py`](../app/api/routes/generation.py#L14-L26), [`web_knowledge.py`](../app/api/routes/web_knowledge.py#L12-L40) и [`workflow.py`](../app/api/routes/workflow.py#L16-L29).
- Скачивание экспорта выполняется по одному `export_id` без проверки владельца в [`outputs.py`](../app/api/routes/outputs.py#L33-L49).
- Общий `ADMIN_API_KEY` защищает загрузку книги и две pilot-операции, но это shared secret, а не пользовательская identity: [`admin_library.py`](../app/api/routes/admin_library.py#L21-L25), [`pilot.py`](../app/api/routes/pilot.py#L17-L21).
- Telegram передаёт `telegram_user_id`, username и display name внутри изменяемого `client_context` в [`telegram_bot/main.py`](../telegram_bot/main.py#L36-L44) и [`telegram_bot/api_client.py`](../telegram_bot/api_client.py#L24-L36). Backend сейчас не аутентифицирует этот контекст.
- `Teacher` — предметная запись без login identity, provider subject, статуса аккаунта или membership: [`app/models/entities.py`](../app/models/entities.py#L37-L49).
- `GenerationRun.teacher_id` допускает `NULL`, а у `ExportedFile`, `WebSearchRun` и `PilotFeedback` нет tenant/owner: [`entities.py`](../app/models/entities.py#L311-L403).

Следствие: текущий API нельзя безопасно открывать нескольким преподавателям как есть.

### 2.1. PR №8 относительно `main`

На дату аудита git refs PR №8 доступны локально: `origin/pr/8/head` указывает на
`e3fcb9b`, а проверенный `origin/main` — на `a5235ce`. PR не объединялся в `main` в
рамках этой работы.

Подтверждённые отличия, относящиеся к identity и authorization:

- PR добавляет общую dependency `require_pilot_access` ко всем `/api/v1` router-ам
  в `app/main.py` и тем самым закрывает открытые endpoint-ы `main` shared-key
  проверкой;
- `app/core/pilot_auth.py` проверяет `PILOT_API_KEY`, caller-provided
  `X-Pilot-User-ID` и allowlist Telegram ID; bot добавляет эти headers в
  `telegram_bot/api_client.py`;
- workflow записывает owner вида `telegram:<id>` в
  `GenerationRun.request_json["_owner_principal"]`, а download endpoint сверяет
  с ним владельца экспорта;
- добавлены fail-closed проверки конфигурации и ограничения доступа к выбранным
  курсам, что полезно сохранить как временное hardening пилота.

При этом общий key аутентифицирует экземпляр bot/adapter, но криптографически не
связывает header с конкретным Telegram update или внутренним пользователем. Утечка
key позволяет указать любой ID из allowlist. В PR по-прежнему нет OIDC identity,
server-side user sessions, memberships, tenant key/RLS, а ownership в JSON не
является нормализованной и защищённой внешним ключом границей данных. Поэтому PR №8
следует считать временным защитным слоем Telegram-пилота, но не целевой web/PWA
identity-архитектурой.

## 3. Контекст и требования

Identity-модель должна одновременно обеспечивать:

- изоляцию материалов, классов, истории запросов и файлов преподавателей;
- приглашения и отзыв доступа без удаления предметных данных;
- web/PWA как основной канал без выдачи JavaScript долгоживущих bearer token;
- тот же пользовательский контекст в Telegram;
- машинный доступ бота, фоновых задач и будущих worker-ов без имитации пользователя;
- аудит привилегированных операций;
- возможность перейти от персональных tenant-ов к школьным без переноса всех данных.

## 4. Решение

### 4.1. Web/PWA: OIDC BFF

PWA и API публикуются под одним site/origin. Backend действует как BFF (backend for frontend).

Поток входа и принятия приглашения:

1. Администратор создаёт invitation для конкретного tenant-а, разрешённой роли и
   ожидаемой identity: предпочтительно `(issuer, subject)`, а если subject заранее
   неизвестен — точного нормализованного email с обязательным `email_verified=true`.
   Проверки только домена недостаточно.
2. Пользователь открывает ссылку со случайным одноразовым токеном не менее 256 бит.
   Backend проверяет его hash, срок и status, создаёт короткую pending enrollment
   transaction, затем немедленно перенаправляет на URL без token. Открытие ссылки
   само по себе не создаёт `User`, не активирует membership и не доказывает identity
   получателя: ссылку можно переслать или перехватить.
3. Backend начинает OIDC Authorization Code + PKCE. Callback проверяет `state`,
   `nonce`, PKCE, подпись ID token, `iss`, `aud`, время и допустимый алгоритм.
4. Идентичность ищется только по паре `(issuer, subject)`. Если invitation был
   привязан к email, callback дополнительно требует точного совпадения verified
   email. Совпадение email никогда не объединяет уже существующие аккаунты.
5. Backend создаёт только pending user/enrollment и ограниченную server-side
   session без активного tenant membership. Такая session разрешает лишь завершение
   enrollment и получает ту же защищённую cookie, но не даёт доступа к tenant-данным.
   PWA показывает пользователю tenant, роль и account, к которым относится invitation.
6. Пользователь явно нажимает «Принять приглашение» в PWA. Запрос требует текущую
   session, synchronizer CSRF token и повторную проверку invitation/enrollment.
7. Только после этого backend в одной транзакции погашает invitation и создаёт либо
   активирует membership. Повторное принятие невозможно.
8. После принятия invitation ограниченная session повышается до обычной только с
   обязательной ротацией случайного session token не менее 256 бит; в БД сохраняется
   только его криптографический hash.
9. Cookie называется `__Host-hsa_session` и всегда имеет
   `Secure; HttpOnly; SameSite=Lax; Path=/`. Атрибут `Domain` не задаётся.
10. Последующие запросы получают `Principal` только после серверной проверки
    сессии и активного membership.

При повторном входе после выхода или истечения сессии приглашённый ранее преподаватель проходит обычный OIDC-вход с PKCE S256. Backend находит существующую пару `(issuer, subject)`, заново проверяет состояние пользователя и членства и выдаёт новую сессию. Одноразовое приглашение требуется при первом вступлении. Для неизвестной пары идентификаторов без действующего приглашения доступ закрыт.

Invitation token является только секретом для продолжения конкретной enrollment
transaction, а не доказательством личности или согласием вступить в tenant. Token
не должен попадать в access/application logs, analytics или `Referer`; для страниц
enrollment задаётся `Referrer-Policy: no-referrer`. При отсутствии verified email
provider-а invitation должен быть заранее привязан к `(issuer, subject)` либо
подтверждён администратором отдельной процедурой — автоматического fallback на
совпадение display name/домена нет.

Tenant и роль берутся из server-side invitation record, а не из URL или формы.
Обычный invitation в пилоте может выдать только tenant role из явного allowlist;
`content_editor`/`platform_admin` назначаются отдельной recent-auth/MFA-защищённой
административной операцией и не кодируются в invitation link.

OIDC access/refresh token для базового входа не нужны после проверки callback и не должны сохраняться. Если позднее появится интеграция с provider API, её token storage проектируется отдельно с envelope encryption и минимальными scopes.

### 4.2. Серверный `Principal`

Минимальный контракт:

```text
Principal
  actor_type: user | service
  user_id: UUID | null
  tenant_id: UUID | null
  membership_id: UUID | null
  tenant_roles: set[teacher | tenant_admin]
  platform_roles: set[content_editor | platform_admin]
  service_principal_id: UUID | null
  session_id: UUID | null
  channel: web | telegram | service
  authenticated_at: timestamp
```

Правила:

- `tenant_id`, `user_id` и роли никогда не принимаются из JSON, query string или обычных caller headers;
- переключение tenant допустимо только на сервере после проверки membership;
- platform role не даёт неявный доступ к содержимому tenant-а;
- support-доступ к данным пользователя требует отдельного ограниченного по времени grant и audit event;
- suspended user, tenant, membership или revoked session немедленно блокируют запрос;
- отсутствие principal означает отказ, кроме явно перечисленных public health endpoints.

### 4.3. Сессия

Ниже приведены только исходные кандидаты для обсуждения closed pilot. Это не
подтверждённые требования и не значения существующего окружения; каждое значение
должно быть конфигурируемым и утверждено владельцем до реализации:

| Параметр | Предложение |
|---|---:|
| Idle timeout | 12 часов |
| Absolute lifetime | 7 суток |
| Telegram link intent | 10 минут |
| Invitation token | 72 часа |
| Ротация session token | после входа, повышения привилегий и смены tenant |
| Одновременные сессии | не более 5 на пользователя |

Обязательные свойства:

- logout отзывает текущую session server-side;
- «выйти со всех устройств» отзывает все sessions пользователя;
- изменение роли, блокировка membership и компрометация вызывают отзыв затронутых sessions;
- token hash сравнивается constant-time;
- session хранит только минимальные метаданные устройства; полный IP без необходимости не сохраняется;
- cookie не используется для cross-origin API;
- API-ответы с персональными данными имеют `Cache-Control: no-store`.

### 4.4. CSRF, CORS и XSS

Для `POST`, `PUT`, `PATCH`, `DELETE` с browser session обязательны одновременно:

- synchronizer CSRF token, связанный с session, в отдельном header;
- строгая проверка `Origin` по allowlist;
- JSON content type для JSON endpoint-ов;
- CORS только для известного PWA origin, без wildcard с credentials.

CSRF не заменяет XSS-защиту. Нужны Content Security Policy, экранирование пользовательского/LLM-контента, запрет raw HTML по умолчанию и отсутствие token в `localStorage`.

### 4.5. Роли и область действия

| Роль | Scope | Назначение | Не даёт автоматически |
|---|---|---|---|
| `teacher` | tenant | Свои/разрешённые tenant-данные, генерация, экспорт, feedback | Управление библиотекой, другими tenant-ами |
| `tenant_admin` | tenant | Membership и настройки школьного tenant-а | Platform administration, чтение tenant-контента без продуктовой причины |
| `content_editor` | platform | Проверка, загрузка, индексация и публикация глобальных источников | Доступ к частным классам и генерациям |
| `platform_admin` | platform | Пользователи, инциденты, системные настройки, audit | Постоянный скрытый доступ к содержимому преподавателя |
| service principal | explicit scopes | Telegram adapter, worker, scheduler | Интерактивный вход, произвольное делегирование пользователя |

Роли additive, deny-by-default. Права проверяются не через разбросанные сравнения строк, а через централизованные policy functions с resource scope и ownership.

### 4.6. Telegram

Текущий `client_context` остаётся полезным для UX/telemetry, но объявляется недоверенным и не участвует в авторизации.

Целевой поток привязки — двухстороннее подтверждение владения двумя активными
каналами, а не автоматическая активация по одному deep-link token:

1. Вошедший web-пользователь с недавней аутентификацией выбирает «Подключить
   Telegram».
2. Backend создаёт случайный одноразовый link intent token не менее 256 бит и
   хранит только hash, `user_id`, `tenant_id`, expiry и state=`created`.
3. Пользователь открывает deep link бота в прямом private chat. `/link <code>` в
   group, supergroup, channel, forum topic или сообщении без `from_user` всегда
   отклоняется. Bot берёт Telegram ID только из проверенного update, а не из текста,
   username или caller header.
4. Bot обращается к backend как service principal с узкими scopes
   `telegram.link.redeem`. Для последующих запросов ассистенту используется отдельное право
   `assistant.invoke_for_linked_user`. Backend атомарно погашает token как
   transport secret, записывает наблюдаемый `(bot_id, telegram_user_id)` и переводит
   intent в `pending_confirmation`, но ещё не создаёт active link.
5. PWA получает pending confirmation и показывает вошедшему пользователю, какой
   Telegram account будет привязан. Пользователь должен явно подтвердить операцию
   из текущей web session; запрос защищён CSRF и recent-auth проверкой.
6. Только после PWA confirmation backend в одной транзакции повторно проверяет срок,
   user, tenant, отсутствие другого active link и создаёт связь со state=`active`.
   Неподтверждённый intent истекает без предоставления доступа.
7. Каждый assistant/feedback запрос bot передаёт Telegram ID по
   аутентифицированному service-каналу; backend сам разрешает его в активный
   user/membership.
8. Блокировка user/membership, отзыв link или service credential немедленно
   прекращает доступ.

Link token не доказывает, что открывший его Telegram account принадлежит владельцу
web-учётной записи: ссылку можно переслать. Он доказывает лишь знание token и
контроль Telegram chat в момент вызова bot-а. Обязательное подтверждение в уже
аутентифицированной PWA связывает обе стороны и предотвращает активацию чужого
Telegram account по пересланной ссылке.

Запрещено:

- саморегистрация только по Telegram ID;
- активация link до явного подтверждения в PWA;
- linking из group/supergroup/channel/forum вместо прямого private chat;
- доверять username, display name, `client_context` или `X-User-ID`;
- использовать общий pilot key как доказательство identity конечного пользователя;
- позволять bot service principal выбирать произвольный `user_id`;
- отправлять link token в логи.

Для пилота достаточно ротируемого service credential через TLS. В зрелом контуре предпочтительны workload identity или mTLS; credential должен быть отдельным от Telegram bot token.

### 4.7. Фоновые задачи

Worker получает service principal с конкретными scopes. Задача содержит неизменяемые `tenant_id`, `requested_by_user_id`, `request_id` и resource ID, сформированные backend-ом. Worker устанавливает DB context в транзакции и не может обработать ресурс другого tenant-а только по переданному UUID.

### 4.8. Audit

Записываются минимум:

- login success/failure без token и credential;
- invitation create/accept/revoke;
- session revoke и изменение ролей;
- Telegram link/unlink;
- загрузка, проверка, публикация и переиндексация источников;
- support grant и каждый доступ по нему;
- административные экспорт/удаление/блокировка;
- authorization deny для чувствительных операций.

Audit event содержит actor, tenant scope, action, target type/ID, outcome, request ID, timestamp и очищенные metadata. Тексты запросов, документы, session/link token и секреты в audit не записываются.

## 5. Рассмотренные альтернативы

### JWT в `localStorage`

Отклонено для PWA: повышает последствия XSS, усложняет мгновенный отзыв и безопасную ротацию. JWT допустим позднее для строго контролируемых machine-to-machine интеграций с коротким TTL и audience, но не как браузерная сессия пилота.

### Собственные пароли

Отклонено на этапе пилота: добавляет хранение password hash, reset, anti-bruteforce, MFA и recovery. OIDC передаёт эти обязанности специализированному provider.

### Общий API key плюс user ID в header

Отклонено как целевая модель: key доказывает приложение/канал, но не конечного пользователя; подмена ID приводит к горизонтальному доступу.

### Только application checks без PostgreSQL RLS

Недостаточно: один пропущенный ownership filter открывает IDOR. Цель — defense in depth: policy layer, tenant-aware foreign keys и RLS. Подробности — в [`TENANT_DATA_MODEL.md`](TENANT_DATA_MODEL.md).

## 6. Последствия

Положительные:

- секреты identity не доступны PWA JavaScript;
- отзыв доступа действует server-side;
- web и Telegram разрешаются в один `User`/`Membership`;
- platform roles отделены от tenant roles;
- схема допускает школьные аккаунты после пилота.

Цена решения:

- нужны новые таблицы identity/session/audit;
- все endpoint-ы и service queries должны принимать `Principal`;
- rollout RLS требует миграции данных и тестов connection pool;
- бот должен получить service authentication и linking flow;
- необходимо выбрать и настроить внешний OIDC provider.

## 7. Открытые решения владельца

Для планирования пилота владельцу предстоит выбрать:

1. OIDC provider и обязательность MFA для platform roles.
2. Разрешённые email/домены, ответственного за invitations и recovery.
3. Подтверждение модели пилота: персональный tenant на каждого из 3–4 преподавателей.
4. Idle/absolute session lifetime.
5. Сроки хранения generation history, feedback, audit и экспортов.
6. Кто может выдавать support grant и должен ли пользователь подтверждать его.
7. Допустимо ли преподавателю просматривать полный текст страниц лицензированных учебников или только цитируемые фрагменты.
8. Требования к локализации/резидентности identity и audit данных.

## 8. Последовательность внедрения после согласования этапа

1. На синтетических данных проверить вход приглашённых пользователей, отзыв сессий и изоляцию двух преподавателей. Для этого подходят имитатор OIDC и отдельная тестовая БД. [Матрица доступа](AUTHORIZATION_MATRIX.md).
2. Перед подключением пилотных аккаунтов проверить выбранного поставщика входа, сроки хранения и фактические права участников. [Критерии приёмки](IDENTITY_TENANCY_ACCEPTANCE.md).
3. Перед переносом существующих данных собрать инвентаризацию, установить владельцев записей и воспроизвести перенос и восстановление на отдельном стенде. [План переноса данных](TENANT_DATA_MODEL.md).
