import json
import uuid

from app.core.config import Settings
from app.services.runtime_readiness import runtime_readiness_checks


KEY = "pilot-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ-strong"
ADMIN = "admin-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ-strong"


def check_map(settings, env):
    return {item.code: item.ok for item in runtime_readiness_checks(settings, env)}


def production_settings(tmp_path, **overrides):
    values = {
        "app_env": "production",
        "auto_create_tables": False,
        "pilot_api_key": KEY,
        "admin_api_key": ADMIN,
        "telegram_allowed_user_ids": "10001",
        "telegram_course_bindings_json": json.dumps(
            {
                "10001": {
                    "social_studies": {"class_course_id": str(uuid.uuid4())},
                }
            }
        ),
        "generation_provider": "http",
        "generation_http_base_url": "https://generation.invalid/v1",
        "generation_http_api_key": "synthetic-test-key",
        "output_storage_dir": str(tmp_path / "generated_outputs"),
        "output_min_free_mb": 1,
    }
    values.update(overrides)
    return Settings(**values)


def production_env(tmp_path, **overrides):
    values = {
        "RAILWAY_SERVICE_ID": "synthetic-service",
        "RAILWAY_VOLUME_MOUNT_PATH": str(tmp_path),
        "EXPORT_INVENTORY_CONFIRMED": "true",
        "EXPORT_BACKUP_CONFIRMED": "true",
        "OUTPUT_STORAGE_MIGRATION_CONFIRMED": "true",
    }
    values.update(overrides)
    return values


def test_production_readiness_accepts_complete_synthetic_configuration(tmp_path):
    checks = check_map(production_settings(tmp_path), production_env(tmp_path))
    assert checks
    assert all(checks.values())


def test_production_readiness_fails_closed_on_release_blockers(tmp_path):
    settings = production_settings(
        tmp_path,
        app_env="dev",
        auto_create_tables=True,
        pilot_api_key="weak",
        admin_api_key="weak",
        telegram_allowed_user_ids="",
        telegram_course_bindings_json="{}",
        generation_provider="template",
        output_storage_dir=str(tmp_path.parent / "outside-volume"),
    )
    env = production_env(
        tmp_path,
        EXPORT_INVENTORY_CONFIRMED="false",
        EXPORT_BACKUP_CONFIRMED="false",
        OUTPUT_STORAGE_MIGRATION_CONFIRMED="false",
    )
    checks = check_map(settings, env)
    for code in (
        "production_mode",
        "schema_mutation_disabled",
        "pilot_key",
        "admin_key",
        "separate_keys",
        "pilot_allowlist",
        "course_bindings",
        "generation_provider",
        "durable_output_storage",
        "export_inventory",
        "backup_restore",
        "storage_migration",
    ):
        assert checks[code] is False


def test_non_production_skips_production_only_gate():
    checks = runtime_readiness_checks(Settings(app_env="test"), {})
    assert [item.code for item in checks] == ["production_gate"]
    assert checks[0].ok is True


def test_production_readiness_rejects_legacy_root_outside_volume(tmp_path):
    outside = tmp_path.parent / "outside-legacy"
    settings = production_settings(
        tmp_path,
        output_legacy_storage_roots_json=json.dumps([str(outside)]),
    )
    checks = check_map(settings, production_env(tmp_path))
    assert checks["durable_output_storage"] is False
