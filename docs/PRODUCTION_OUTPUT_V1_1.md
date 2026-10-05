# Production Output Layer v1.1

## Назначение

v1.1 превращает структурированный педагогический JSON в печатные файлы.

Канонический формат - **DOCX**. PDF строится из того же DOCX через LibreOffice,
поэтому содержание teacher/student версий не расходится между форматами.

## Поддерживаемые артефакты

- урок;
- проверочная/самостоятельная;
- рабочий лист;
- домашнее задание;
- IDEA Enhancer.

## Аудитории

- `teacher` - ключи, критерии, методические заметки, источники;
- `student` - без ответов и teacher-only информации.

## Форматы

- DOCX;
- PDF.

## Шаблоны

### `school_clean`

Основной A4-шаблон. Умеренные поля, читаемая типографика, цветовые информационные
блоки, маркировка teacher/student.

### `compact_print`

Более плотная версия для экономной печати.

## API

### Список шаблонов

```text
GET /api/v1/outputs/templates
```

### Экспорт результата генерации

```text
POST /api/v1/outputs/render
```

Пример:

```json
{
  "generation_run_id": "<uuid>",
  "audience": "student",
  "formats": ["docx", "pdf"],
  "template_name": "school_clean"
}
```

### Экспорт inline-артефакта

```json
{
  "artifact": {
    "artifact_type": "homework",
    "title": "Домашнее задание",
    "grade": 9,
    "subject": "SOCIAL_STUDIES",
    "purpose": "consolidation",
    "estimated_minutes": 15,
    "student_instruction": "...",
    "success_criteria": ["..."]
  },
  "artifact_type": "homework",
  "audience": "student",
  "formats": ["docx", "pdf"]
}
```

### Скачать файл

```text
GET /api/v1/outputs/files/{export_id}
```

### Файлы конкретного generation run

```text
GET /api/v1/outputs/runs/{run_id}
```

## Аудит экспорта

`exported_files` хранит:

- generation run;
- тип артефакта;
- аудиторию;
- формат;
- шаблон и его версию;
- SHA-256;
- размер;
- путь;
- дату создания.

## Требования окружения

DOCX:

```text
python-docx
```

PDF:

```text
LibreOffice / soffice
```

Если LibreOffice отсутствует, DOCX остаётся доступным, а PDF export возвращает
явную ошибку/предупреждение вместо фиктивного PDF.

## Принцип печати

1. Сначала формируется teacher/student JSON.
2. Из него строится DOCX.
3. PDF конвертируется **из этого DOCX**.
4. Файлы хешируются и регистрируются.
5. Для релиза шаблонов используется визуальный render-QA.

## Безопасность ключей

Output layer не создаёт student version из teacher DOCX удалением текста.
Он получает уже очищенный student artifact от Pedagogy Core и рендерит его отдельно.
Это снижает риск случайно оставить ответы в скрытом/видимом содержимом файла.
