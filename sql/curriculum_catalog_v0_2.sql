-- Migration: Curriculum Catalog v0.2
-- Adds pedagogical enrichment fields promised by SOP-20.

ALTER TABLE topics ADD COLUMN IF NOT EXISTS common_examples jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE topics ADD COLUMN IF NOT EXISTS counterexamples jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS interdisciplinary_links (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_id uuid NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    related_subject varchar(100) NOT NULL,
    related_topic varchar(500),
    link_type varchar(100),
    description text NOT NULL,
    strength varchar(50) NOT NULL DEFAULT 'optional'
);
CREATE INDEX IF NOT EXISTS ix_interdisciplinary_links_topic_id ON interdisciplinary_links(topic_id);
CREATE INDEX IF NOT EXISTS ix_interdisciplinary_links_subject ON interdisciplinary_links(related_subject);
