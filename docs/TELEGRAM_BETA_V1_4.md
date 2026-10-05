# Telegram Adapter v1.4 / Pilot 1.0

## Режим

Для первого пилота используется long polling.

Причины:
- не нужен домен;
- не нужен публичный HTTPS webhook;
- быстро запускается;
- подходит для небольшой группы тестировщиков.

При масштабировании перейти на webhook.

## Команды

- `/start`
- `/help`
- `/status`
- `/feedback`
- `/whoami`

## Основные кнопки

- Создать урок
- Проверочная
- Рабочий лист
- Домашнее задание
- ОГЭ / ЕГЭ
- Найти в библиотеке
- Улучшить идею
- Ошибка / отзыв

Свободный ввод остаётся главным режимом.

## Архитектура

Telegram не импортирует педагогическую бизнес-логику.

Он вызывает:

```text
POST /api/v1/assistant
```

и скачивает outputs через backend.

## Feedback

Пользовательский отзыв сохраняется в PostgreSQL:

```text
pilot_feedback
```

Admin endpoints защищены `ADMIN_API_KEY`.

## Production generation

v1.4 добавляет provider:

```env
GENERATION_PROVIDER=openai_responses
OPENAI_GENERATION_MODEL=gpt-5.6-terra
```

Student versions для assessment/worksheet/homework создаются backend-ом из teacher artifact,
поэтому модель не может случайно оставить ответы в ученической версии.
