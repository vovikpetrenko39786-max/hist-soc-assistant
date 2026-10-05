-- Exam Mapping v0.5
CREATE TABLE IF NOT EXISTS exam_models (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), model_key varchar(160) NOT NULL UNIQUE,
 exam varchar(30) NOT NULL, subject varchar(100) NOT NULL, year integer NOT NULL,
 status varchar(40) NOT NULL, total_tasks integer, max_primary_score integer,
 source_url text NOT NULL, change_source_url text, notes text,
 metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_exam_models_lookup ON exam_models(exam,subject,year,status);

CREATE TABLE IF NOT EXISTS exam_resources (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), exam_model_id uuid NOT NULL REFERENCES exam_models(id) ON DELETE CASCADE,
 resource_type varchar(80) NOT NULL, title varchar(500) NOT NULL, url text NOT NULL,
 source_year integer, status varchar(50) NOT NULL DEFAULT 'official', notes text,
 metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
 CONSTRAINT uq_exam_resource UNIQUE(exam_model_id,resource_type,url)
);

CREATE TABLE IF NOT EXISTS codifier_elements (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), exam_model_id uuid NOT NULL REFERENCES exam_models(id) ON DELETE CASCADE,
 code varchar(50) NOT NULL, section varchar(300), normalized_label text NOT NULL,
 source_reference text NOT NULL, verification_status varchar(80) NOT NULL,
 metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
 CONSTRAINT uq_exam_codifier_code UNIQUE(exam_model_id,code)
);
CREATE INDEX IF NOT EXISTS ix_codifier_model_code ON codifier_elements(exam_model_id,code);

CREATE TABLE IF NOT EXISTS exam_tasks (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), exam_model_id uuid NOT NULL REFERENCES exam_models(id) ON DELETE CASCADE,
 task_key varchar(80) NOT NULL, task_number integer, title varchar(500) NOT NULL,
 response_type varchar(100), max_score integer, skill_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
 content_scope jsonb NOT NULL DEFAULT '{}'::jsonb, verification_status varchar(80) NOT NULL,
 source_reference text NOT NULL, notes text, metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
 CONSTRAINT uq_exam_task_key UNIQUE(exam_model_id,task_key)
);

CREATE TABLE IF NOT EXISTS topic_exam_mappings (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), topic_id uuid NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
 exam_model_id uuid NOT NULL REFERENCES exam_models(id) ON DELETE CASCADE,
 codifier_element_id uuid REFERENCES codifier_elements(id) ON DELETE CASCADE,
 task_keys jsonb NOT NULL DEFAULT '[]'::jsonb, mapping_status varchar(80) NOT NULL,
 confidence double precision, evidence_type varchar(80) NOT NULL, evidence_reference text,
 notes text, metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
 CONSTRAINT uq_topic_exam_codifier UNIQUE(topic_id,exam_model_id,codifier_element_id)
);
CREATE INDEX IF NOT EXISTS ix_topic_exam_mapping_status ON topic_exam_mappings(mapping_status);
