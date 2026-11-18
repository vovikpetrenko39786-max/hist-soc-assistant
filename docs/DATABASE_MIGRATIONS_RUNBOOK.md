# Runbook миграций базы данных

**Статус:** foundation для новых пустых БД
**Не является:** разрешением применять Alembic к существующей staging/production БД

## 1. Жёсткое ограничение

Ревизия `0001` создаёт текущую ORM-схему на **новой пустой PostgreSQL БД**.

До отдельного согласованного этапа запрещено выполнять на существующей БД:

- `alembic stamp`;
- `alembic upgrade`;
- `alembic downgrade`;
- ручное изменение `alembic_version`;
- удаление или переименование существующих таблиц, индексов и extensions.

Причина: исторически схема создавалась через `Base.metadata.create_all()` и
отдельные SQL-файлы из `sql/`. Репозиторий не содержит доказательства, какие из
них и в каком порядке применены к production.

## 2. Что подтверждает foundation

- Alembic использует async SQLAlchemy и `Base.metadata` всех моделей;
- `0001_empty_database_orm_bootstrap` содержит явные `op.create_table` и
  `op.create_index`, а не скрытый вызов `create_all`;
- `0001` fail-closed останавливается до изменений, если в `public` уже есть
  прикладная таблица, view, materialized view, sequence или enum;
- на одноразовой БД проходят `upgrade head`, повторный upgrade, `alembic check`,
  `downgrade base` и новый upgrade;
- создаётся extension `vector` и 36 ORM-таблиц;
- downgrade удаляет ORM-таблицы и enum-типы, но намеренно не удаляет shared
  extension `vector`;
- `scripts/schema_inventory.py` собирает read-only fingerprint схемы без
  вывода строки подключения.
- runtime image содержит `alembic.ini` и каталог `migrations`, но не запускает
  migration автоматически при старте API.

## 3. Что foundation намеренно не утверждает

Ревизия `0001` не объявляется точной копией существующей production-схемы.

Не согласованы и не включены как canonical:

- исторические server-side UUID/defaults из ручных SQL;
- `ON DELETE CASCADE/SET NULL`, отсутствующие в ORM;
- часть CHECK constraints и partial unique indexes из `sql/`;
- FTS/GiN и operational composite indexes;
- HNSW expression indexes: в репозитории одновременно встречаются размерности
  384 и 1536, а ORM хранит `Vector()` без фиксированной размерности;
- данные seed и отметка о том, какие исторические SQL уже применены.

Выбор embedding model/dimension и канонических retrieval indexes оформляется
отдельным ADR и миграцией.

## 4. Локальная проверка только на одноразовой БД

Smoke-скрипт принимает только точный URL:

```text
postgresql+asyncpg://ci:ci_test@127.0.0.1:55433/hist_soc_migration_test
```

Любой другой host, port, database, user или password отклоняется до соединения.

Пример локального контейнера:

```bash
docker run --name hist-soc-migration-pg \
  -e POSTGRES_USER=ci \
  -e POSTGRES_PASSWORD=ci_test \
  -e POSTGRES_DB=hist_soc_migration_test \
  -p 127.0.0.1:55433:5432 \
  -d pgvector/pgvector:0.8.7-pg16

MIGRATION_TEST_DATABASE_URL=postgresql+asyncpg://ci:ci_test@127.0.0.1:55433/hist_soc_migration_test \
DATABASE_URL=postgresql+asyncpg://ci:ci_test@127.0.0.1:55433/hist_soc_migration_test \
python scripts/ci_migration_smoke.py
```

После проверки контейнер удаляется. Эти команды нельзя переориентировать на
Railway или shared database.

## 5. Read-only inventory существующего окружения

Inventory-скрипт:

- начинает read-only transaction;
- устанавливает statement timeout 15 секунд;
- читает extensions, tables, columns, defaults, constraints и index definitions;
- фиксирует Alembic revision, если таблица существует;
- не читает строки пользовательских таблиц;
- не выводит password, host или полный URL;
- формирует детерминированный SHA-256 fingerprint.

Имя БД и версия PostgreSQL присутствуют в отчёте для диагностики, но исключены
из fingerprint, поэтому одинаковые схемы разных окружений можно сравнивать.

Запуск на production не входит в данный этап. Когда владелец отдельно разрешит
read-only inventory, результат следует сохранять в защищённое место, а в git
помещать только согласованный обезличенный drift report.

## 6. Порядок принятия существующей БД под Alembic

1. Получить read-only inventory и schema-only dump.
2. Зафиксировать PostgreSQL/pgvector versions, extensions и applied SQL history.
3. Создать backup и восстановить его в изолированное окружение.
4. Сравнить snapshot с `0001`: columns, defaults, nullability, FK/on-delete,
   constraints, indexes, enums и vector dimensions.
5. Проверить orphan rows и данные, нарушающие будущие constraints.
6. Подготовить отдельную reconciliation/adoption migration без потери данных.
7. Прогнать migration на восстановленной копии, schema smoke и application tests.
8. Повторить restore drill после migration.
9. Только после review решить, нужен ли `stamp` или реальный upgrade на staging.
10. Production adoption выполняется отдельным заданием с явным разрешением и
    планом roll-forward/rollback.

## 7. Release gate

Миграция не допускается к production, если отсутствует хотя бы одно:

- актуальный schema inventory;
- backup и успешный restore rehearsal;
- drift report с решением по каждому отличию;
- проверка данных на новые constraints;
- staging rehearsal точной release revision;
- подтверждённые canonical embedding dimension и indexes;
- назначенный оператор и окно восстановления;
- явное разрешение владельца проекта.

## 8. Текущий runtime

`AUTO_CREATE_TABLES` пока не удалён, чтобы этот foundation PR не совмещал
создание новой миграционной цепочки с потенциально ломающим production
переключением startup policy. Следующий отдельный шаг после inventory — запретить
`create_all` в staging/production и проверять Alembic revision в readiness.
