-- v1.0 — universal pedagogical artifact layer.
-- Reuses generation_runs and generated_materials.
CREATE INDEX IF NOT EXISTS ix_generation_runs_task_status_created
    ON generation_runs(task_type, status, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_generated_materials_type_status
    ON generated_materials(material_type, status);
