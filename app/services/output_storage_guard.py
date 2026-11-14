"""Prevent new exports from silently going to ephemeral Railway disk.

Only checks that the configured output directory is beneath the mount declared
by Railway. The deployment operator must separately verify that the mount is a
backed-up persistent volume and that legacy exports were inventoried.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path


class OutputStorageConfigurationError(RuntimeError):
    pass


def output_directory(
    configured_path: str,
    *,
    app_env: str = "dev",
    volume_mount_path: str | None = None,
    on_railway: bool = False,
) -> Path:
    """Return an absolute output directory, refusing unsafe production paths.

    This validation does NOT write/create directories or establish that a mount
    has backups. The caller may mkdir only after validation succeeds.
    """
    if not configured_path or not configured_path.strip():
        raise OutputStorageConfigurationError("output_storage_dir must not be empty")

    configured = Path(configured_path).expanduser()
    production = on_railway or app_env.lower() in {"prod", "production"}
    if not production:
        return configured.resolve()

    if not configured.is_absolute():
        raise OutputStorageConfigurationError(
            "Production OUTPUT_STORAGE_DIR must be an absolute path on a persistent volume"
        )
    if not volume_mount_path:
        raise OutputStorageConfigurationError(
            "Production requires a declared RAILWAY_VOLUME_MOUNT_PATH"
        )
    declared_volume = Path(volume_mount_path)
    if not declared_volume.is_absolute():
        raise OutputStorageConfigurationError("Declared volume path must be absolute")
    volume = declared_volume.resolve()
    output = configured.resolve()
    if volume.parent == volume:
        raise OutputStorageConfigurationError(
            "Declared persistent volume must not be a filesystem root"
        )
    if not volume.is_dir():
        raise OutputStorageConfigurationError("Declared persistent volume directory is missing")
    if output == volume or not output.is_relative_to(volume):
        raise OutputStorageConfigurationError(
            "OUTPUT_STORAGE_DIR must be a subdirectory inside the declared persistent volume"
        )
    return output


def allocate_export_directory(base: Path, run_part: str) -> Path:
    """Allocate a fresh directory; never replace a previous exported document."""
    destination = base / run_part / uuid.uuid4().hex
    destination.mkdir(parents=True, exist_ok=False)
    return destination


def current_output_directory(settings) -> Path:
    """Validate against process environment without ever logging credentials."""
    return output_directory(
        settings.output_storage_dir,
        app_env=settings.app_env,
        volume_mount_path=os.getenv("RAILWAY_VOLUME_MOUNT_PATH"),
        on_railway=bool(os.getenv("RAILWAY_SERVICE_ID") or os.getenv("RAILWAY_ENVIRONMENT_ID")),
    )


def require_free_export_space(destination: Path, *, minimum_free_mb: int = 64,
                              disk_usage=None) -> int:
    """Fail before rendering when available disk space is too small.

    No directories are created here. Resolve the nearest existing ancestor so
    newly configured output subdirectories can be checked before first export.
    This is a preflight, not a reservation: concurrent writers require quotas
    and monitoring; also maintain backups of the volume separately.
    """
    import shutil

    if not isinstance(minimum_free_mb, int) or not 1 <= minimum_free_mb <= 1024:
        raise OutputStorageConfigurationError("Invalid OUTPUT_MIN_FREE_MB setting")
    target = Path(destination).resolve()
    while not target.exists() and target.parent != target:
        target = target.parent
    if not target.is_dir():
        raise OutputStorageConfigurationError("Output storage parent is not a directory")
    try:
        usage = (disk_usage or shutil.disk_usage)(target)
        available = int(usage.free)
    except (OSError, ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise OutputStorageConfigurationError("Cannot verify free space for output storage") from exc
    if available < minimum_free_mb * 1024 * 1024:
        raise OutputStorageConfigurationError(
            "Not enough free space for safe document export; preserve books and retry later"
        )
    return available
