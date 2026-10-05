CREATE TABLE IF NOT EXISTS pilot_feedback (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel varchar(50) NOT NULL DEFAULT 'telegram',
    category varchar(50) NOT NULL DEFAULT 'feedback',
    user_external_id varchar(200),
    username varchar(200),
    display_name varchar(300),
    text text NOT NULL,
    last_request text,
    generation_run_id uuid REFERENCES generation_runs(id),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status varchar(50) NOT NULL DEFAULT 'new',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_pilot_feedback_status_created
    ON pilot_feedback(status, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_pilot_feedback_user
    ON pilot_feedback(user_external_id);

-- Recommended production semantic index if using text-embedding-3-small (1536 dims).
CREATE INDEX IF NOT EXISTS ix_source_chunks_embedding_hnsw_1536
    ON source_chunks
    USING hnsw ((embedding::vector(1536)) vector_cosine_ops)
    WHERE embedding_status = 'ready' AND embedding_dim = 1536;
