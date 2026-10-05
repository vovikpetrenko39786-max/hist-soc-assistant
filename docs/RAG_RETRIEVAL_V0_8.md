# RAG Retrieval Engine v0.8

## Реализовано

- embeddings для `SourceChunk`;
- hybrid retrieval: PostgreSQL Full Text Search + pgvector;
- lexical-only, vector-only и exact modes;
- strict-source режим;
- reranking по релевантности и качеству источника;
- verified page references;
- safe exact-quote flag;
- endpoint для чтения конкретной извлечённой страницы.

## Embedding providers

### `hash`

Офлайн, детерминированный provider для тестов и разработки.

Он **не является production semantic embedding model**.

Поэтому источник после полной индексации получает:

`rag_ready_dev`

а не `rag_ready`.

### `http`

Production adapter к совместимому `/embeddings` endpoint.

Конфигурация:

```env
EMBEDDING_PROVIDER=http
EMBEDDING_HTTP_BASE_URL=https://embedding-service.example/v1
EMBEDDING_HTTP_API_KEY=...
EMBEDDING_HTTP_MODEL=...
EMBEDDING_DIM=384
```

## API

### Создать embeddings для источника

```text
POST /api/v1/retrieval/sources/{source_id}/embed
```

### Hybrid search

```text
POST /api/v1/retrieval/search
```

Пример:

```json
{
  "query": "признаки социального института",
  "subject": "SOCIAL_STUDIES",
  "grade": 10,
  "level": "basic",
  "mode": "hybrid",
  "top_k": 8
}
```

### Strict Source

```json
{
  "query": "признаки социального института",
  "source_key": "SOC_10_STATE_2026",
  "strict_source": true,
  "mode": "hybrid"
}
```

### Exact quote

```json
{
  "query": "социальный институт",
  "source_key": "SOC_10_STATE_2026",
  "strict_source": true,
  "mode": "exact",
  "exact_phrase": "социальный институт"
}
```

`quote_safe=true` означает только одно: буквальная строка реально присутствует
в сохранённом chunk. Semantic retrieval никогда автоматически не становится цитатой.

### Проверить страницу

```text
GET /api/v1/sources/{source_id}/pages/{page_number_pdf}
```

## Ранжирование

Reranker учитывает:

1. lexical rank;
2. vector rank;
3. `authority_rank`;
4. `source.status`;
5. актуальность источника;
6. точное совпадение;
7. приоритет источника в Topic Card.

## Страницы

Hit содержит:

- `page_pdf_start/end`;
- `page_print_start/end`, если печатная нумерация достоверно известна;
- `page_reference_status`.

Страница не угадывается моделью.

## Главное правило

RAG возвращает доказательную базу ответа.

LLM может пересказывать найденное содержание, но:
- не выдумывает страницу;
- не выдаёт semantic snippet за дословную цитату;
- в strict-source режиме не использует другой учебник.
