-- v0.9 — grounded generation audit trail

CREATE TABLE IF NOT EXISTS generation_runs (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_type varchar(100) NOT NULL,
    topic_id uuid REFERENCES topics(id),
    class_course_id uuid REFERENCES class_courses(id),
    teacher_id uuid REFERENCES teachers(id),
    provider varchar(100) NOT NULL,
    model varchar(200) NOT NULL,
    prompt_hash varchar(128) NOT NULL,
    request_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    context_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_manifest jsonb NOT NULL DEFAULT '[]'::jsonb,
    output_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    quality_report jsonb NOT NULL DEFAULT '{}'::jsonb,
    status varchar(50) NOT NULL DEFAULT 'created',
    dry_run boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_generation_runs_topic_created
    ON generation_runs(topic_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_generation_runs_provider_model
    ON generation_runs(provider, model);

CREATE INDEX IF NOT EXISTS ix_generation_runs_status
    ON generation_runs(status);
