-- Source Catalog v0.6
ALTER TABLE sources ADD COLUMN IF NOT EXISTS source_key varchar(150);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sources_source_key ON sources(source_key) WHERE source_key IS NOT NULL;
ALTER TABLE sources ALTER COLUMN author TYPE text;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS fpu_number varchar(100);
ALTER TABLE sources ADD COLUMN IF NOT EXISTS isbn varchar(50);
ALTER TABLE sources ADD COLUMN IF NOT EXISTS source_url text;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS authority_rank integer NOT NULL DEFAULT 50;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS verification_status varchar(100);
ALTER TABLE sources ADD COLUMN IF NOT EXISTS rollout_status varchar(100);
ALTER TABLE sources ADD COLUMN IF NOT EXISTS availability_status varchar(100);
ALTER TABLE sources ADD COLUMN IF NOT EXISTS coverage varchar(100);
CREATE INDEX IF NOT EXISTS ix_sources_fpu_number ON sources(fpu_number);
CREATE INDEX IF NOT EXISTS ix_sources_isbn ON sources(isbn);
CREATE INDEX IF NOT EXISTS ix_sources_authority_rank ON sources(authority_rank);
CREATE INDEX IF NOT EXISTS ix_sources_verification_status ON sources(verification_status);
CREATE INDEX IF NOT EXISTS ix_sources_rollout_status ON sources(rollout_status);
CREATE INDEX IF NOT EXISTS ix_sources_availability_status ON sources(availability_status);
CREATE INDEX IF NOT EXISTS ix_sources_coverage ON sources(coverage);
