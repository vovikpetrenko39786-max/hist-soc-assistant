-- Source ingestion / PDF pipeline v0.7

ALTER TABLE sources ADD COLUMN IF NOT EXISTS ingestion_status varchar(100);
ALTER TABLE sources ADD COLUMN IF NOT EXISTS ingested_at timestamptz;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS text_char_count integer;

CREATE INDEX IF NOT EXISTS ix_sources_ingestion_status ON sources(ingestion_status);

CREATE TABLE IF NOT EXISTS source_pages (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    page_number_pdf integer NOT NULL,
    page_label varchar(100),
    printed_page integer,
    text text NOT NULL DEFAULT '',
    text_hash varchar(64),
    char_count integer NOT NULL DEFAULT 0,
    has_text boolean NOT NULL DEFAULT false,
    extraction_method varchar(50) NOT NULL DEFAULT 'pymupdf',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_source_page_pdf_number UNIQUE(source_id, page_number_pdf)
);
CREATE INDEX IF NOT EXISTS ix_source_pages_source ON source_pages(source_id);
CREATE INDEX IF NOT EXISTS ix_source_pages_printed ON source_pages(printed_page);
CREATE INDEX IF NOT EXISTS ix_source_pages_text_hash ON source_pages(text_hash);

CREATE TABLE IF NOT EXISTS source_sections (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    parent_section_id uuid REFERENCES source_sections(id) ON DELETE SET NULL,
    toc_level integer NOT NULL DEFAULT 1,
    title varchar(1000) NOT NULL,
    start_page_pdf integer NOT NULL,
    end_page_pdf integer,
    printed_page_start integer,
    printed_page_end integer,
    order_index integer NOT NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_source_sections_source ON source_sections(source_id);
CREATE INDEX IF NOT EXISTS ix_source_sections_start_page ON source_sections(start_page_pdf);

CREATE TABLE IF NOT EXISTS source_ingestion_runs (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    status varchar(100) NOT NULL,
    original_filename varchar(1000),
    stored_file_path text,
    file_hash varchar(64),
    file_size_bytes integer,
    extraction_method varchar(100),
    page_count integer,
    text_char_count integer,
    pages_with_text integer,
    sections_created integer NOT NULL DEFAULT 0,
    chunks_created integer NOT NULL DEFAULT 0,
    needs_ocr boolean NOT NULL DEFAULT false,
    error_message text,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_source_ingestion_runs_source ON source_ingestion_runs(source_id);
CREATE INDEX IF NOT EXISTS ix_source_ingestion_runs_status ON source_ingestion_runs(status);
CREATE INDEX IF NOT EXISTS ix_source_ingestion_runs_hash ON source_ingestion_runs(file_hash);

ALTER TABLE source_chunks ADD COLUMN IF NOT EXISTS section_id uuid REFERENCES source_sections(id) ON DELETE SET NULL;
ALTER TABLE source_chunks ADD COLUMN IF NOT EXISTS page_pdf_end integer;
ALTER TABLE source_chunks ADD COLUMN IF NOT EXISTS page_print_end integer;
ALTER TABLE source_chunks ADD COLUMN IF NOT EXISTS text_hash varchar(64);
ALTER TABLE source_chunks ADD COLUMN IF NOT EXISTS char_count integer;
ALTER TABLE source_chunks ADD COLUMN IF NOT EXISTS embedding_status varchar(50) NOT NULL DEFAULT 'pending';

CREATE INDEX IF NOT EXISTS ix_source_chunks_section ON source_chunks(section_id);
CREATE INDEX IF NOT EXISTS ix_source_chunks_text_hash ON source_chunks(text_hash);
CREATE INDEX IF NOT EXISTS ix_source_chunks_embedding_status ON source_chunks(embedding_status);
