"""Sanitized, fail-closed production readiness checks."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from app.core.pilot_auth import is_strong_shared_key, parse_course_bindings
from app.core.telegram_access import parse_allowed_user_ids
from app.services.export_integrity import ExportIntegrityError, storage_roots
from app.services.output_storage_guard import (
    OutputStorageConfigurationError,
    output_directory,
    require_free_export_space,
)


@dataclass(frozen=True)
class ReadinessCheck:
    code: str
    ok: bool
    detail: str


def _confirmed(env: Mapping[str, str], name: str) -> bool:
    return env.get(name, "").strip().casefold() == "true"


def runtime_readiness_checks(
    settings,
    env: Mapping[str, str] | None = None,
) -> list[ReadinessCheck]:
    """Return only non-sensitive release facts suitable for a public endpoint."""
    environment = os.environ if env is None else env
    on_railway = bool(
        environment.get("RAILWAY_SERVICE_ID")
        or environment.get("RAILWAY_ENVIRONMENT_ID")
    )
    production = on_railway or settings.app_env.strip().casefold() in {
        "prod",
        "production",
    }
    if not production:
        return [
            ReadinessCheck(
                "production_gate",
                True,
                "Production-only configuration gate is not required in this environment.",
            )
        ]

    checks: list[ReadinessCheck] = []

    app_env_ok = settings.app_env.strip().casefold() in {"prod", "production"}
    checks.append(
        ReadinessCheck(
            "production_mode",
            app_env_ok,
            "APP_ENV identifies production." if app_env_ok else "APP_ENV must be production.",
        )
    )
    checks.append(
        ReadinessCheck(
            "schema_mutation_disabled",
            not settings.auto_create_tables,
            (
                "Automatic schema creation is disabled."
                if not settings.auto_create_tables
                else "AUTO_CREATE_TABLES must be false in production."
            ),
        )
    )

    pilot_key_ok = is_strong_shared_key(settings.pilot_api_key)
    admin_key_ok = is_strong_shared_key(settings.admin_api_key)
    keys_are_separate = bool(
        pilot_key_ok
        and admin_key_ok
        and settings.pilot_api_key != settings.admin_api_key
    )
    checks.extend(
        [
            ReadinessCheck(
                "pilot_key",
                pilot_key_ok,
                (
                    "Pilot key meets the runtime policy."
                    if pilot_key_ok
                    else "Strong PILOT_API_KEY is required."
                ),
            ),
            ReadinessCheck(
                "admin_key",
                admin_key_ok,
                (
                    "Admin key meets the runtime policy."
                    if admin_key_ok
                    else "Strong ADMIN_API_KEY is required."
                ),
            ),
            ReadinessCheck(
                "separate_keys",
                keys_are_separate,
                (
                    "Pilot and admin keys are distinct."
                    if keys_are_separate
                    else "Pilot and admin keys must be strong and distinct."
                ),
            ),
        ]
    )

    try:
        allowed_ids = parse_allowed_user_ids(settings.telegram_allowed_user_ids)
        allowlist_ok = bool(allowed_ids)
    except ValueError:
        allowlist_ok = False
    checks.append(
        ReadinessCheck(
            "pilot_allowlist",
            allowlist_ok,
            (
                "Pilot allowlist is non-empty and valid."
                if allowlist_ok
                else "A valid pilot allowlist is required."
            ),
        )
    )

    try:
        bindings = parse_course_bindings(settings.telegram_course_bindings_json)
        bindings_ok = bool(bindings)
    except ValueError:
        bindings_ok = False
    checks.append(
        ReadinessCheck(
            "course_bindings",
            bindings_ok,
            (
                "User-scoped course bindings are valid."
                if bindings_ok
                else "Valid course bindings are required."
            ),
        )
    )

    provider = settings.generation_provider.strip().casefold()
    provider_ok = (
        provider == "openai_responses" and bool(settings.openai_api_key)
    ) or (
        provider == "http"
        and bool(settings.generation_http_base_url)
        and bool(settings.generation_http_api_key)
    )
    checks.append(
        ReadinessCheck(
            "generation_provider",
            provider_ok,
            (
                "Production generation provider is configured."
                if provider_ok
                else "A credentialed production generation provider is required."
            ),
        )
    )

    try:
        output = output_directory(
            settings.output_storage_dir,
            app_env=settings.app_env,
            volume_mount_path=environment.get("RAILWAY_VOLUME_MOUNT_PATH"),
            on_railway=on_railway,
        )
        storage_roots(
            str(output),
            settings.output_legacy_storage_roots_json,
            required_parent=environment.get("RAILWAY_VOLUME_MOUNT_PATH"),
        )
        require_free_export_space(
            output,
            minimum_free_mb=settings.output_min_free_mb,
        )
        output_ok = True
    except (ExportIntegrityError, OutputStorageConfigurationError, OSError):
        output_ok = False
    checks.append(
        ReadinessCheck(
            "durable_output_storage",
            output_ok,
            (
                "Output storage is volume-scoped and has reserve capacity."
                if output_ok
                else "Durable output storage is not ready."
            ),
        )
    )

    for name, code, detail in (
        (
            "EXPORT_INVENTORY_CONFIRMED",
            "export_inventory",
            "Legacy export inventory is confirmed.",
        ),
        (
            "EXPORT_BACKUP_CONFIRMED",
            "backup_restore",
            "Restorable database and file backups are confirmed.",
        ),
        (
            "OUTPUT_STORAGE_MIGRATION_CONFIRMED",
            "storage_migration",
            "Output storage migration is confirmed.",
        ),
    ):
        confirmed = _confirmed(environment, name)
        checks.append(
            ReadinessCheck(
                code,
                confirmed,
                detail if confirmed else "Required operator confirmation is missing.",
            )
        )

    return checks
