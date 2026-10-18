-- Migration: Topic Card provenance and reference-slice fields.
-- Additive only; existing catalog data is preserved.

ALTER TABLE topics ADD COLUMN IF NOT EXISTS content_summary text;
ALTER TABLE topics ADD COLUMN IF NOT EXISTS suitable_activities jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE topics ADD COLUMN IF NOT EXISTS provenance jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE topics ADD COLUMN IF NOT EXISTS derivation_status varchar(50) NOT NULL DEFAULT 'pending_enrichment';
ALTER TABLE topics ADD COLUMN IF NOT EXISTS verification_status varchar(50) NOT NULL DEFAULT 'pending_verification';