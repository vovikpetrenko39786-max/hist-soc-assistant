-- v1.3 — controlled external web fallback audit log.

CREATE TABLE IF NOT EXISTS web_search_runs (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_id uuid REFERENCES topics(id),
    generation_run_id uuid REFERENCES generation_runs(id),
    policy varchar(50) NOT NULL,
    scope varchar(50) NOT NULL,
    provider varchar(100) NOT NULL,
    model varchar(200) NOT NULL,
    query text NOT NULL,
    allowed_domains jsonb NOT NULL DEFAULT '[]'::jsonb,
    response_text text,
    sources_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    status varchar(50) NOT NULL DEFAULT 'created',
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS ix_web_search_runs_topic_created
    ON web_search_runs(topic_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_web_search_runs_policy_scope
    ON web_search_runs(policy, scope);

CREATE INDEX IF NOT EXISTS ix_web_search_runs_status
    ON web_search_runs(status);
