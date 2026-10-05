-- v1.1 - Production Output Layer

CREATE TABLE IF NOT EXISTS exported_files (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    generation_run_id uuid REFERENCES generation_runs(id),
    artifact_type varchar(100) NOT NULL,
    audience varchar(50) NOT NULL,
    file_format varchar(20) NOT NULL,
    template_name varchar(100) NOT NULL,
    template_version varchar(50) NOT NULL,
    file_path text NOT NULL,
    file_name varchar(500) NOT NULL,
    sha256 varchar(64) NOT NULL,
    size_bytes integer NOT NULL,
    status varchar(50) NOT NULL DEFAULT 'ready',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_exported_files_run_created
    ON exported_files(generation_run_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_exported_files_format_template
    ON exported_files(file_format, template_name, template_version);
CREATE INDEX IF NOT EXISTS ix_exported_files_sha256
    ON exported_files(sha256);
