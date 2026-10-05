-- v0.8 — embeddings + hybrid retrieval

ALTER TABLE source_chunks
    ADD COLUMN IF NOT EXISTS embedding_model varchar(200),
    ADD COLUMN IF NOT EXISTS embedding_dim integer,
    ADD COLUMN IF NOT EXISTS embedded_at timestamptz;

CREATE INDEX IF NOT EXISTS ix_source_chunks_embedding_status_model
    ON source_chunks(embedding_status, embedding_model, embedding_dim);

CREATE INDEX IF NOT EXISTS ix_source_chunks_fts_ru
    ON source_chunks
    USING gin (to_tsvector('russian', coalesce(text, '')));

CREATE INDEX IF NOT EXISTS ix_source_chunks_embedding_hnsw_384
    ON source_chunks
    USING hnsw ((embedding::vector(384)) vector_cosine_ops)
    WHERE embedding_status = 'ready' AND embedding_dim = 384;

CREATE INDEX IF NOT EXISTS ix_sources_retrieval_scope
    ON sources(subject, grade, level, status, is_current, authority_rank);
