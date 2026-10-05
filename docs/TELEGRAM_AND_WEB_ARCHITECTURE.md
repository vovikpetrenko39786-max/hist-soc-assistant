# Telegram Bot & Future Web Architecture

## Главный принцип

Telegram и будущий сайт — это интерфейсы одного и того же backend.

Нельзя переносить Curriculum, RAG, SOP, генераторы и Quality Gate внутрь
Telegram handlers. Иначе при появлении сайта придётся переписывать продукт.

Правильная схема:

```text
Telegram / Web
      ↓
Assistant API
POST /api/v1/assistant
      ↓
Natural Language Workflow
      ↓
Curriculum Resolver
      ↓
Topic Card
      ↓
Source Catalog + RAG
      ↓
LLM / tools when required
      ↓
Quality Gate
      ↓
Output Layer
      ↓
Text / DOCX / PDF
```

## Telegram

Telegram-бот отвечает только за:

- получение сообщений;
- inline/reply buttons;
- выбор режима;
- передачу текста backend;
- отображение статуса;
- отправку ответа;
- отправку DOCX/PDF;
- хранение Telegram user ID ↔ internal user ID mapping;
- команды `/start`, `/help`, `/settings`.

Основная педагогическая логика остаётся в backend.

## Пример будущего меню

- Создать урок
- Проверочная / самостоятельная
- Рабочий лист
- Домашнее задание
- Найти в учебнике
- ОГЭ / ЕГЭ
- Мои классы
- Мои материалы
- Настройки
- Помощь

При этом пользователь всегда может просто написать свободный текст без кнопок.

## Natural-language mode

Пример:

> 10 класс, обществознание, социальные институты.
> Сделай полноценный урок и рабочий лист в двух версиях, Word.

Telegram отправляет эту строку в:

```text
POST /api/v1/assistant
```

Backend сам определяет все параметры.

## Knowledge fallback

Рекомендуемая политика:

```text
1. Global Curriculum / Topic Card
2. Локальная библиотека / RAG
3. Официальные актуальные web-источники
4. Общий web search, если это допустимо и действительно нужно
5. Генерация ответа
```

Внешний поиск не должен автоматически заменять библиотеку.

Для нормативных и экзаменационных вопросов сначала используются официальные
источники.

## OpenAI integration

Telegram-бот не должен быть привязан к конкретному диалогу в приложении ChatGPT.

Backend подключается к OpenAI API через server-side API key.

Модель может использовать поддерживаемые API tools, в том числе web search,
когда orchestration layer разрешил внешний поиск.

Секретные ключи никогда не передаются Telegram-клиенту или пользователю.

## Data ownership

Собственная база продукта хранит:

- программы;
- Topic Cards;
- учебники;
- chunks / embeddings;
- пользовательские настройки;
- классы;
- прогресс;
- созданные материалы;
- generation runs.

Это позволяет менять LLM provider без потери данных.

## Updates

Обновление продукта делится на независимые части:

1. Код backend.
2. Telegram UI.
3. Библиотека и индексы.
4. Curriculum datasets.
5. SOP/runtime rules.
6. LLM/provider configuration.
7. Output templates.

Замена одной части не должна требовать переписывания остальных.

## Diagnostics

Production deployment должен иметь:

- structured logs;
- health endpoint;
- error ID для пользовательских ошибок;
- audit `generation_runs`;
- резервное копирование PostgreSQL;
- версии dataset;
- версии prompts/SOP;
- smoke tests после deploy;
- возможность rollback.

## Future Web

Когда появится сайт:

```text
Web frontend
     ↓
тот же /api/v1/assistant
```

Меняются только:

- форма ввода;
- визуальный кабинет;
- история материалов;
- редактор;
- управление библиотекой.

Педагогическое ядро и база остаются теми же.

## Рекомендуемый порядок дальнейшей разработки

```text
v1.2 Natural-language workflow
→ web-search fallback layer
→ Telegram adapter
→ authentication / user profiles
→ production deployment
→ monitoring/backups
→ pilot testing
→ web frontend later
```
