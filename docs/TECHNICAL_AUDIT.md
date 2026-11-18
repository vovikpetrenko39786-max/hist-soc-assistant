# Технический аудит Hist-Soc Assistant

**Дата среза:** 16 ноября 2026 года  
**Аудируемая база:** `main`, коммит `a5235ce8ebff55dc2e6357dd2eb8e2efbc9ab325`  
**PR №8:** git-head `e3fcb9b9c2df94f2f9f7f442a54f504d9455cca8`, merge-base с `main` — `a5235ce8ebff55dc2e6357dd2eb8e2efbc9ab325`  
**Область:** код, схемы, SQL, seed-данные, тесты, документация и локально воспроизводимые проверки. Production Railway, production-БД, секреты и реальные пользовательские данные не изменялись и не читались.

## 1. Как читать выводы

В документе используются три статуса доказательности:

- **Подтверждено** — установлено по коду, git-истории, статическим данным или выполненному локальному тесту.
- **Предположение** — архитектурный вывод или рекомендация, которую ещё требуется подтвердить продуктовым либо эксплуатационным решением.
- **Не проверено** — невозможно установить по репозиторию без доступа к production, владельцу данных или внешней экспертной оценке.

Уровни приоритета:

- **P0** — блокирует безопасный многопользовательский пилот.
- **P1** — должно быть исправлено до или в начале закрытого пилота.
- **P2** — допустимо отложить на ограниченный пилот при явно принятом риске.

## 2. Резюме для владельца проекта

### 2.1. Общая оценка

**Подтверждено.** Проект уже содержит значимый доменный фундамент: FastAPI API, модели учебной программы, каталог источников, PDF-ингест, гибридный retrieval PostgreSQL FTS + pgvector, генерацию по структурированным схемам, эвристические quality gates, DOCX/PDF-экспорт и Telegram-бот. Это не «пустой прототип».

**Подтверждено.** Текущий `main` не готов к многопользовательской эксплуатации. API не имеет пользовательской аутентификации; несколько изменяющих состояние и потенциально дорогих маршрутов общедоступны; запросы по идентификатору не ограничиваются владельцем; экспортируемые файлы не имеют владельца; миграции и резервное восстановление не встроены в релизный процесс. См. подключение маршрутов в [app/main.py](../app/main.py#L25-L38), открытые операции в [app/api/routes/sources.py](../app/api/routes/sources.py#L25-L44) и [app/api/routes/retrieval.py](../app/api/routes/retrieval.py#L24-L34).

**Подтверждено.** PR №8 — крупный и полезный пакет усиления закрытого пилота: 77 файлов, 5 699 добавлений, 110 удалений, 38 коммитов относительно `main`. Он добавляет shared-key/allowlist-контур, readiness/preflight, CI, ограничения экспорта, более профессиональную структуру урока, Telegram-курсы и сценарии восстановления. Однако PR не является полноценной web-auth/tenant-архитектурой и не должен объединяться «как есть» без разбивки, анализа миграций и проверки на staging.

**Подтверждено.** Пять JSON-наборов и их валидаторы дают хорошую основу предметной модели, но не доказывают полноту и педагогическую корректность. В репозитории нет полного текста 17 заявленных учебников; они отмечены как `metadata_only`. Экзаменационные модели имеют статус проекта, а не окончательной версии. Поэтому обещание «работает с проверенными учебниками и материалами ФИПИ» пока нельзя считать выполненным.

### 2.2. Критические проблемы

| Приоритет | Проблема | Последствие |
|---|---|---|
| P0 | Нет web-аутентификации, ролей и обязательной проверки владельца | Чтение/изменение чужих данных и несанкционированные расходы |
| P0 | Открыты ingest, embedding, генерация и web search | Повреждение общей библиотеки, DoS, расход API-квот |
| P0 | Нет строгой tenant-модели и PostgreSQL RLS | Ошибка одного запроса может раскрыть данные другого учителя |
| P0 | Повторный ingest удаляет текущие страницы/чанки до успешной замены | Потеря пригодной индексации при сбое |
| P0 | Нет доказанного production backup/restore и миграционного контура | Невоспроизводимый релиз и риск необратимой потери данных |
| P0 | Экспорты в `main` скачиваются по UUID без проверки владельца/целостности | IDOR и выдача подменённого либо чужого файла |
| P1 | Hash-384 — default embedding и не семантическая production-модель | Низкое качество retrieval при ошибочной конфигурации |
| P1 | Ссылки подтверждают наличие записи в manifest, но не конкретное утверждение | Правдоподобный ответ может не следовать из источника |
| P1 | `strict_source` в разговорном workflow фактически сбрасывается | Нарушается прямое требование учителя использовать конкретный учебник |
| P1 | `quality_failed` в `main` может автоматически экспортироваться | Пользователь получает материал, который система сама отклонила |
| P1 | PDF-конвертация синхронно блокирует async-процесс | Таймауты и деградация API при параллельных запросах |
| P1 | Telegram использует `MemoryStorage` и не ограничивает пользователей | Потеря состояния после рестарта и открытый доступ к боту |
| P1 | Нет PWA/web-интерфейса | Основной целевой канал продукта отсутствует |

### 2.3. Рекомендация

**Предположение/рекомендация.** До закрытого пилота следует развивать модульный монолит, а не микросервисы: FastAPI + PostgreSQL/pgvector + отдельный worker + object storage + PWA. Сначала — идентичность, tenant-изоляция, Alembic, восстановление и неизменяемое хранение файлов; затем — содержание, RAG и методическая оценка; только после этого — пилотная UX-полировка. Целевая схема подробно описана в [ARCHITECTURE.md](ARCHITECTURE.md), этапы — в [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md).

## 3. Методика и выполненные проверки

### 3.1. Проверено

- полное дерево отслеживаемых файлов, `README`, `pyproject.toml`, Docker-конфигурация, SQL и документация;
- API-маршруты, SQLAlchemy-модели, сервисы генерации, retrieval, ingest, web fallback и экспорта;
- JSON seed-данные и их валидаторы;
- ветка PR №8 через git refs и её тройной diff относительно `origin/main`;
- локальные тесты `main`: **137 passed**, 2 предупреждения;
- локальные тесты PR №8: **308 passed**, 1 предупреждение;
- проверки синтаксиса и Ruff `E9,F` для PR №8;
- schema smoke и release smoke PR №8 на одноразовом локальном контейнере `pgvector/pgvector:0.8.7-pg16`;
- двукратный seed на одноразовой БД: первый запуск создаёт данные, второй не создаёт дубликаты.

Контейнер и тестовая БД были локальными и удаляемыми; соединения с Railway не выполнялись.

### 3.2. Не проверено

- правила защиты ветки `main` и обязательность проверок при слиянии. Состояние самого PR №8 и результат его CI перепроверены 18 ноября, см. раздел 12;
- фактическая схема, расширения, индексы, объёмы и целостность production PostgreSQL;
- наличие и конфигурация production `pgvector`, резервных копий, PITR и успешного restore drill;
- Railway services, variables, volume mounts, replicas, health checks и журналы;
- реальные PDF учебников, права на их хранение/обработку и соответствие метаданных файлам;
- production-провайдеры LLM/embeddings, модели, квоты, стоимость и качество;
- визуальное качество большого набора реальных DOCX/PDF;
- внешняя предметная и методическая экспертиза seed-данных;
- локальный restore drill PR №8: на хосте отсутствовали `pg_dump`/`pg_restore`; в CI такой шаг заявлен.

## 4. Текущее устройство системы

### 4.1. Компоненты

| Слой | Реализация в `main` | Оценка повторного использования |
|---|---|---|
| API | FastAPI, async SQLAlchemy | Сохранить, усилить auth/policy/errors/idempotency |
| БД | PostgreSQL, ручные SQL-скрипты | Сохранить PostgreSQL; заменить управление схемой на Alembic |
| Векторы | pgvector + HNSW casts | Сохранить; унифицировать размерность и версионирование индекса |
| Каталог | JSON seeds + SQL import | Сохранить предметную модель; добавить ревизии и редакционный workflow |
| PDF ingest | PyMuPDF, страницы/разделы/чанки | Переработать в асинхронный versioned pipeline |
| Retrieval | FTS + vector + metadata filters | Сохранить как основу; добавить eligibility, reranking и evals |
| Генерация | template/HTTP/OpenAI providers, Pydantic | Сохранить provider abstraction; переработать orchestration/validation |
| Quality gates | Структурные и эвристические проверки | Сохранить как первый слой, не считать предметной экспертизой |
| DOCX | `python-docx` | Сохранить renderer, добавить версии шаблонов и golden tests |
| PDF | LibreOffice subprocess | Вынести в worker, добавить visual checks и лимиты |
| Telegram | aiogram polling | Оставить адаптером; заменить identity/session boundary |
| Web/PWA | Отсутствует | Создать новый клиент после auth/tenant foundation |

### 4.2. Зависимости и сборка

**Подтверждено.** Основные зависимости объявлены широкими диапазонами в [pyproject.toml](../pyproject.toml): FastAPI, SQLAlchemy 2, asyncpg/psycopg, Pydantic 2, pgvector, PyMuPDF, httpx, python-docx, pymorphy3 и aiogram. Lock-файла нет. Это создаёт риск нерепродуцируемой сборки.

**Подтверждено.** В репозитории отсутствуют Alembic, очередь фоновых заданий, Redis, S3-клиент, OpenTelemetry/Sentry, web frontend и PWA manifest/service worker.

**Рекомендация.** Зафиксировать версии через lock-файл, внедрить dependency scanning и воспроизводимую сборку до пилота. Не обновлять зависимости одновременно с большим функциональным merge.

## 5. PostgreSQL, pgvector и данные

### 5.1. Схема и миграции

**Подтверждено.** По умолчанию `AUTO_CREATE_TABLES=True`, а приложение вызывает `Base.metadata.create_all()` при старте: [app/core/config.py](../app/core/config.py#L10) и [app/main.py](../app/main.py#L14-L20). Это создаёт недостающие таблицы, но не является миграцией существующей схемы и не фиксирует историю изменения данных.

**Подтверждено.** SQL-скрипты версионированы именами файлов, но не имеют общей таблицы миграций, автоматического порядка применения, downgrade и атомарного release gate. Один скрипт создаёт `uuid-ossp`, но создание extension `vector` в SQL проекта не найдено.

**Подтверждено.** Размерность в модели не закреплена: `Vector()` в [app/models/entities.py](../app/models/entities.py#L262-L286). При этом HNSW-индекс в [sql/retrieval_v0_8.sql](../sql/retrieval_v0_8.sql#L15-L18) приводит к `vector(384)`, а [sql/pilot_telegram_v1_4.sql](../sql/pilot_telegram_v1_4.sql#L22-L26) — к `vector(1536)`. Это явный риск drift и несовместимости индекса с выбранной моделью.

**P0-рекомендация.** Ввести Alembic как единственный способ изменения production-схемы; отдельную миграцию extensions; `schema_version` и `content_revision`; preflight/backup/restore; запрет `create_all` вне тестов/dev.

### 5.2. Многопользовательская модель

**Подтверждено.** В модели существуют `Teacher`, `ClassGroup.teacher_id`, `ClassCourse.teacher_id`, `GeneratedMaterial.teacher_id` и опциональные ссылки `GenerationRun.teacher_id/class_course_id`: [app/models/entities.py](../app/models/entities.py#L37-L136) и [app/models/entities.py](../app/models/entities.py#L311-L359). Это полезная заготовка, но не полноценная идентичность пользователя.

**Подтверждено.** Нет таблиц account/identity/session/membership/role/organization. `ExportedFile` не имеет владельца, `WebSearchRun` не tenant-scoped. Уникальности и внешние ключи не доказывают принадлежность одной организации. PostgreSQL RLS отсутствует.

**Подтверждено.** Сервисы памяти и API получают `class_course_id` и ищут запись по одному UUID без teacher predicate, например [app/services/memory.py](../app/services/memory.py#L17-L27) и [app/api/routes/context.py](../app/api/routes/context.py#L13-L18). Это IDOR-класс риска.

**Вывод.** Добавление одного `teacher_id` в несколько таблиц не достаточно. Нужны единый `principal`, tenant-aware foreign keys, обязательный policy layer и RLS как защита второго рубежа.

### 5.3. Сохранность

**Не проверено.** Репозиторий не доказывает, что production использует persistent Railway volume для БД или файлов, что включены backups/PITR и что восстановление регулярно проверяется.

**Рекомендация.** До любых миграций владелец должен предоставить обезличенный schema dump, список extensions/индексов, политику backup/PITR и протокол успешного восстановления на отдельном окружении.

## 6. Учебная база и обработка источников

### 6.1. Покрытие каталогов

Локальные валидаторы прошли. По [учебному seed](../data/official_curriculum_seed_2026_2027.json), [каталогу источников](../data/source_catalog_seed_2026_2027.json), [экзаменационному seed](../data/exam_mapping_seed_2027.json) и их валидаторам подтверждено:

- учебная программа v0.4: 12 curricula, 42 раздела, 307 тем, 1 535 результатов, 1 769 связей topic-skill, 226 exam links, 244 межпредметные связи;
- concepts заполнены только для 154 из 307 тем;
- каталог v0.6: 18 источников, 17 правил соответствия и 3 документированных пробела;
- 17 учебников представлены метаданными (`metadata_only`), а не полным текстом;
- экзаменационная база v0.5: 4 модели, 75 элементов кодификатора, 12 типов заданий; модели помечены `project`;
- зафиксированы пробелы: региональный компонент истории 5 класса, полное соответствие углублённого обществознания 10 класса ФПУ и частичное покрытие 11 класса.

Связанные описания: [OFFICIAL_CURRICULUM_BASE_2026_2027.md](OFFICIAL_CURRICULUM_BASE_2026_2027.md), [SOURCE_CATALOG_V0_6.md](SOURCE_CATALOG_V0_6.md), [EXAM_MAPPING_V0_5.md](EXAM_MAPPING_V0_5.md). Валидаторы находятся в [validate_curriculum_dataset.py](../scripts/validate_curriculum_dataset.py), [validate_source_catalog.py](../scripts/validate_source_catalog.py) и [validate_exam_mapping.py](../scripts/validate_exam_mapping.py).

**Не проверено.** Статус `verified_fpu` в seed — утверждение данных проекта; в ходе аудита не выполнялась независимая сверка каждого ISBN/издания с актуальным ФПУ. Нет подписанного методистом реестра ревизий.

### 6.2. Ingest

**Подтверждено.** Pipeline сохраняет PDF, считает SHA-256, извлекает страницы/оглавление/чанки через PyMuPDF и обновляет статус источника. Текстовые PDF поддерживаются; OCR только диагностируется как необходимый. См. [app/services/source_ingestion.py](../app/services/source_ingestion.py) и [app/services/pdf_ingestion.py](../app/services/pdf_ingestion.py).

**P0. Подтверждено.** При повторной загрузке код удаляет существующие `SourceChunk`, `SourceSection` и `SourcePage` до завершения новой обработки: [app/services/source_ingestion.py](../app/services/source_ingestion.py#L128-L130). Обработчик ошибки сохраняет failed-статус отдельным commit. При сбое пригодная старая индексация может быть утрачена.

**Подтверждено.** Отсутствуют явные лимиты размера/числа страниц, очередь заданий, идемпотентный job ledger, антивирусная проверка, quota и versioned blue/green activation. Временный путь на источник может конфликтовать при параллельном ingest; старые файлы могут оставаться сиротами.

**Рекомендация.** Загружать новую `source_revision` неизменяемо, обрабатывать в worker, валидировать и только атомарно переключать `active_revision_id`. Не удалять последнюю рабочую ревизию при ошибке.

### 6.3. Embeddings и retrieval

**Подтверждено.** Default provider — детерминированный `hash-384-v1`, который сам код называет development/non-semantic: [app/core/config.py](../app/core/config.py#L16-L17), [app/services/embeddings.py](../app/services/embeddings.py#L42-L43). Production-quality provider задаётся универсальным HTTP endpoint и в репозитории не сконфигурирован.

**Подтверждено.** Retrieval сочетает PostgreSQL FTS и vector similarity, фильтрует предмет/класс/уровень/статус и учитывает topic/source scope: [app/services/retrieval.py](../app/services/retrieval.py). Это разумная база. Однако eligibility не требует во всех путях одновременно подтверждённой редакционной ревизии, production embedding и разрешённого типа источника. Нет отдельного reranker и измеренного retrieval benchmark.

**Вывод.** Сам факт использования pgvector не доказывает семантическое качество. Нужны закреплённая модель, размерность, `embedding_revision`, golden query set и метрики Recall@k/nDCG/citation coverage.

## 7. Понимание естественного языка

**Подтверждено.** [app/services/natural_language_workflow.py](../app/services/natural_language_workflow.py) извлекает тип материала, предмет, класс, тему, режим и длительность регулярными выражениями/ключевыми словами. Для ограниченного русского pilot vocabulary это полезный deterministic слой.

**Подтверждено.** Нет устойчивого диалогового state machine, классификатора намерения с тестовой матрицей, LLM fallback для сложных формулировок и обязательного clarification loop. При нехватке данных workflow часто выбирает lesson по умолчанию.

**P1. Подтверждено.** Даже когда запрос распознаёт конкретный источник, в generation request передаётся `strict_source=False`: [app/services/natural_language_workflow.py](../app/services/natural_language_workflow.py#L486). Таким образом, фраза «только по этому учебнику» не становится строгим системным инвариантом.

**Подтверждено.** `client_context` принимается схемой, но в `main` не является доверенной identity/ownership границей: [app/schemas/workflow.py](../app/schemas/workflow.py#L11-L13). Нельзя строить изоляцию на клиентском словаре.

**Рекомендация.** Использовать двухступенчатый NLU: deterministic parser для точных сущностей + structured LLM parser; затем policy/validation и явное уточнение при низкой уверенности. Память курса должна читаться только из tenant-scoped БД, а не из недоверенного prompt context.

## 8. Генерация, источники и методический контроль

### 8.1. Что уже хорошо

- артефакты валидируются Pydantic-схемами;
- template provider даёт воспроизводимый offline режим;
- generation context передаёт manifest и запрещает придумывать новые ссылки;
- lesson gate проверяет сумму времени, результаты, действия учеников, formative assessment, рефлексию, концепты и принадлежность ссылок manifest;
- сохраняются provider/model/prompt hash/input/output/quality report в `GenerationRun`;
- web fallback начинает с набора официальных доменов.

См. [app/services/generation_context.py](../app/services/generation_context.py#L216-L241), [app/services/quality_gate.py](../app/services/quality_gate.py) и [app/services/grounded_generation.py](../app/services/grounded_generation.py).

### 8.2. Ограничения

**Подтверждено.** Gate проверяет структуру и совпадение metadata/page с manifest, но не доказывает, что каждое содержательное утверждение следует из указанного фрагмента. Нет claim-level entailment, проверки корректности ответов/ключей, возрастной уместности и реальной выполнимости плана за 45 минут.

**Подтверждено.** OpenAI pedagogy adapter заменяет `source_references` первыми элементами manifest: [app/services/openai_pedagogy.py](../app/services/openai_pedagogy.py#L87-L103) и [app/services/openai_pedagogy.py](../app/services/openai_pedagogy.py#L171). Это доказывает доступность источника, но не его использование в конкретном тезисе.

**P1. Подтверждено.** `main` допускает автоматический рендер статуса `quality_failed`: [app/services/natural_language_workflow.py](../app/services/natural_language_workflow.py#L525-L540).

**Подтверждено.** При отсутствии официальных результатов допускается general web fallback и добавляется предупреждение: [app/services/web_knowledge.py](../app/services/web_knowledge.py#L397-L415). Для экзаменационных и нормативных материалов одного предупреждения недостаточно: general web должен быть запрещён по policy.

**Предположение.** Для пилота нужен не «LLM-судья как единственная истина», а каскад: schema validation → deterministic policy → citation entailment → task answer verification → методическая rubric → ручное подтверждение учителя. На высокорисковых материалах публикация без ручного просмотра запрещена.

## 9. API и безопасность

### 9.1. Аутентификация и авторизация

**P0. Подтверждено.** В `main` все основные routers подключены без dependency аутентификации: [app/main.py](../app/main.py#L25-L38). Admin-key защищает только отдельные admin/pilot routes; это не закрывает legacy ingest/embed/generation routes.

**P0. Подтверждено.** Нет rate limiting, cost quota, idempotency key, CSRF/session защиты, OIDC/JWT validation и audit trail административных действий.

**P0. Подтверждено.** Ресурсы извлекаются по UUID без обязательного owner predicate. Непредсказуемость UUID не является авторизацией.

### 9.2. Файлы и внешние данные

**P0. Подтверждено.** [app/api/routes/outputs.py](../app/api/routes/outputs.py#L33-L49) возвращает `FileResponse` по DB path без проверки владельца, checksum и containment внутри storage root.

**Подтверждено.** Web-содержимое попадает в generation context. Явной модели защиты от prompt injection внутри найденного документа нет. Allowlist доменов уменьшает, но не устраняет риск компрометации сайта/страницы.

**Рекомендация.** Все внешние данные считать недоверенными; отделять instructions от evidence; санитизировать и лимитировать; хранить snapshot/hash; не позволять retrieved text изменять system policy.

### 9.3. Секреты и приватность

**Подтверждено.** Значения секретов в ходе аудита не читались. В коде секреты приходят через settings/env.

**Подтверждено.** Telegram feedback хранит идентификаторы и текст запроса; формальной retention policy, consent flow и удаления данных пользователя не найдено.

**Не проверено.** Соответствие 152-ФЗ и иным требованиям зависит от состава реальных данных, оператора, региона хранения и договоров с провайдерами. Требуется отдельная правовая проверка; этот аудит не является юридическим заключением.

## 10. DOCX/PDF и хранение результатов

**Подтверждено.** DOCX renderer создаёт учительскую и ученическую версии, таблицы, стили и источники: [app/services/docx_renderer.py](../app/services/docx_renderer.py). Это пригодная основа.

**Подтверждено.** Путь результата детерминирован по run/slug/audience; повторный рендер может перезаписать файл, на который уже ссылается старая запись. Файловая система и commit БД не образуют транзакцию: [app/services/output_service.py](../app/services/output_service.py).

**P1. Подтверждено.** PDF создаётся через синхронный `subprocess.run` LibreOffice с timeout внутри async request path: [app/services/pdf_export.py](../app/services/pdf_export.py#L36-L47). Это блокирует event loop.

**Подтверждено.** Нет object-storage versioning, signed URLs, retention/cleanup job, антивирусного контроля результата, визуальной регрессии и golden document suite.

**Не проверено.** Наличие persistent output volume в production и качество кириллических шрифтов на фактическом Railway image.

## 11. Telegram

**Подтверждено.** Бот использует aiogram polling, `MemoryStorage` и concurrency limit 20: [telegram_bot/main.py](../telegram_bot/main.py#L234-L243). Состояние диалога теряется при рестарте.

**P1. Подтверждено.** `telegram_admin_ids` объявлен, но в `main` не обеспечивает allowlist. Любой пользователь, нашедший бота, может инициировать запросы. Backend не признаёт `client_context` доказательством личности.

**Вывод.** Telegram следует оставить дополнительным каналом. Учётная запись должна жить в общей identity-модели; Telegram связывается одноразовым кодом, а бот вызывает API с service credential и серверным principal, который нельзя подменить заголовком клиента.

## 12. Разбор PR №8

### 12.1. Доступность и отличие от `main`

**Подтверждено 18 ноября 2026 года.** GitHub показывает открытый черновик «Integrate PRs #1–7 into a tested release candidate» из ветки `integration/release-candidate-2026-11-14` в `main`. Голова PR — `e3fcb9b`, база — `a5235ce`. Разница составляет 38 коммитов и 77 файлов (+5 699/−110). GitHub сообщает об отсутствии конфликта слияния. Список опубликованных ревью пуст. Проверка «Hist-Soc regression checks» на этом коммите завершилась успешно. [Запуск CI](https://github.com/vovikpetrenko39786-max/hist-soc-assistant/actions/runs/43814534238).

**По отчёту автора PR.** В изолированном staging создан DOCX по синтетическому учебнику и проверена его пагинация. Данные о staging приведены в описании PR. Для проверки прав на реальные учебники, качества уроков в нескольких классах и восстановления фактических рабочих данных нужны отдельные свидетельства.

Ссылки: [PR №8](https://github.com/vovikpetrenko39786-max/hist-soc-assistant/pull/8), [изменения PR](https://github.com/vovikpetrenko39786-max/hist-soc-assistant/pull/8/files), [head-коммит](https://github.com/vovikpetrenko39786-max/hist-soc-assistant/commit/e3fcb9b9c2df94f2f9f7f442a54f504d9455cca8).

### 12.2. Полезные изменения

**Подтверждено по diff PR.** Добавлены:

- глобальный pilot access dependency для `/api/v1`, закрытый allowlist и различие pilot/admin key;
- `/ready` с проверкой схемы/pgvector и production preflight;
- запрет экспортировать `quality_failed`, owner checks для части outputs и проверка checksum/path/storage;
- уникальные render directories и проверка durable volume/free space;
- более строгая валидация ссылок на источник;
- расширенная схема урока: ФГОС-связь, профессиональный рассказ учителя, ожидаемые вопросы учеников и три методических варианта;
- course bindings и `/courses` для Telegram, private-chat middleware;
- CI с PostgreSQL/pgvector, schema smoke, authenticated export smoke, double seed и restore drill.

Примеры PR-кода: [pilot_auth.py](https://github.com/vovikpetrenko39786-max/hist-soc-assistant/blob/e3fcb9b9c2df94f2f9f7f442a54f504d9455cca8/app/core/pilot_auth.py), [runtime_readiness.py](https://github.com/vovikpetrenko39786-max/hist-soc-assistant/blob/e3fcb9b9c2df94f2f9f7f442a54f504d9455cca8/app/services/runtime_readiness.py), [workflow CI](https://github.com/vovikpetrenko39786-max/hist-soc-assistant/blob/e3fcb9b9c2df94f2f9f7f442a54f504d9455cca8/.github/workflows/tests.yml).

### 12.3. Что PR №8 не решает

**P0. Подтверждено по diff.** Shared pilot key + caller-supplied `X-Pilot-User-ID` не является безопасной web identity: при утечке общего ключа можно выдать себя за любого allowlisted пользователя.

**P0. Подтверждено по diff.** Глобальная authentication dependency не равна role authorization. Pilot-пользователь всё ещё может вызвать общие mutating/cost routes ingest, embed, generic generation и web search, если маршрут не получил отдельную admin policy.

**Подтверждено по diff.** Ownership экспорта хранится в JSON `GenerationRun.request_json["_owner_principal"]`, а не в индексированном FK. Legacy rows остаются особым случаем.

**Подтверждено по diff.** Нет OIDC, sessions, RLS, tenant foreign keys, Alembic, object storage, job queue, rate limits и PWA.

**Подтверждено по локальному тесту.** Schema/release smoke прошли. Restore drill локально не подтверждён из-за отсутствия клиентских PostgreSQL utilities. В smoke-скрипте очистка синтетической fixture выполняется не через `finally`; при падении теста fixture может остаться в одноразовой CI БД. Это P2-гигиена теста, не production-дефект.

### 12.4. Рекомендация по интеграции

**Рекомендация.** Не объединять PR №8 автоматически. Разбить или последовательно перенести группы изменений:

1. CI/readiness/preflight и output integrity;
2. schema/model/rendering урока и соответствующие тесты;
3. Telegram allowlist/course binding как временный pilot adapter;
4. auth/ownership — только после проектирования web identity и tenant migration;
5. отдельно проверить SQL/data migrations на копии production snapshot.

## 13. Тесты и эксплуатационная зрелость

**Подтверждено.** Существующие тесты хорошо покрывают deterministic domain paths и регрессии PR. Однако большая часть тестов — unit/service tests; нет браузерных E2E, реальной concurrency, chaos/retry, RLS, нагрузочных, security scanning и набора методических evals.

**Подтверждено.** Полный Ruff по `main` сообщил 149 замечаний; среди них много форматных/import/B008, но также broad exceptions и unused code. PR проходит ограниченный correctness profile `E9,F`, а не полный quality profile.

**Рекомендация.** Ввести quality baseline без массового рефакторинга: сначала запрет новых ошибок, затем отдельные малые PR. Критерии приемки перечислены в [ACCEPTANCE_TESTS.md](ACCEPTANCE_TESTS.md).

## 14. Матрица «оставить или переработать»

| Компонент | Решение | Причина |
|---|---|---|
| FastAPI + async SQLAlchemy | Оставить | Подходит нагрузке пилота и доменной сложности |
| PostgreSQL | Оставить | Транзакционность, FTS, JSONB и RLS |
| pgvector | Оставить | Достаточен при закреплённой модели и evals |
| Реляционная модель curriculum/topics | Оставить и версионировать | Сильная доменная база |
| JSON validators/seeds | Оставить как import artifact | Нужен редакционный approval/revision workflow |
| Ручные SQL migrations | Заменить | Нет надёжного upgrade/rollback/audit trail |
| PDF extraction | Переработать | Нужны OCR, версии, limits, jobs и atomic activation |
| Hybrid retrieval | Развить | Нужны eligibility/rerank/evaluation |
| Provider abstraction | Оставить | Удобна для тестов и смены модели |
| Natural-language regex parser | Оставить первым слоем | Недостаточен как единственный NLU |
| Quality gates | Оставить первым слоем | Не проверяют факты и методику полностью |
| DOCX renderer | Оставить и тестировать | Уже даёт полезный результат |
| LibreOffice conversion | Вынести в worker | Блокирует API и требует sandbox/limits |
| Local output storage | Заменить object storage | Версии, durability, signed access, retention |
| Telegram bot | Оставить каналом | Не должен быть identity/system core |
| PR №8 pilot shared key | Только временно | Не подходит PWA и долгосрочной изоляции |

## 15. Действия владельца проекта

До начала implementation-волн владелец должен:

1. Предоставить read-only инвентаризацию Railway: services, environments, deploy commit, volume mounts, health/readiness, без передачи секретных значений.
2. Предоставить обезличенный schema-only dump, версии PostgreSQL/pgvector, список таблиц/индексов/extensions и row counts.
3. Подтвердить backup/PITR и выполнить restore drill в отдельном окружении с протоколом времени и целостности.
4. Утвердить identity-вариант для PWA, домены, роли `teacher/content_editor/admin` и правила приглашения 3–4 пилотных учителей.
5. Дать список пилотных курсов, классов, выбранных учебников и регионального компонента.
6. Передать реестр разрешённых файлов учебников: edition/ISBN/FPU revision/hash/license/право обработки; не секреты и не токены.
7. Назначить предметного редактора и методиста, которые подпишут corpus revision и rubric/eval set.
8. Утвердить политику ФИПИ: проект/финал, дата актуальности, запрет выдавать проект за действующую спецификацию.
9. Утвердить retention/export/delete policy для запросов, отзывов, файлов и Telegram identifiers; провести юридическую проверку персональных данных.
10. Установить бюджеты LLM/web search, лимиты на пользователя и правило остановки при перерасходе.
11. Проверить правила защиты `main` и выбрать группы изменений PR №8 для отдельного ревью.
12. Не передавать секреты в задачи, документацию и логи; при подозрении на прежнюю публикацию выполнить отдельную ротацию.

## 16. Итоговый go/no-go

**Сейчас: NO-GO для многопользовательского production и закрытого пилота с реальными данными.** Причины: P0 auth/tenant, mutating routes, ingest replacement, download ownership и недоказанный restore.

**GO для следующего инженерного этапа:** документация, threat model, миграционный дизайн, локальная/staging-разработка и формирование проверенного учебного корпуса.

**Условия допуска к закрытому пилоту** приведены в [разделе 14 дорожной карты](DEVELOPMENT_ROADMAP.md#14-обязательные-gate-перед-пилотом) и [разделе 15 критериев приёмки](ACCEPTANCE_TESTS.md#15-итоговый-pilot-gate).
