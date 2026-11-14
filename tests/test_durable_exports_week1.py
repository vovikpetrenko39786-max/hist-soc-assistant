"""Safety requirements for durable exports and non-overwriting filenames."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.output_storage_guard import (
    OutputStorageConfigurationError,
    allocate_export_directory,
    current_output_directory,
    output_directory,
)


def test_local_development_supports_relative_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert output_directory("data/outputs", app_env="dev") == tmp_path / "data/outputs"


def test_production_relative_path_is_rejected(tmp_path):
    with pytest.raises(OutputStorageConfigurationError, match="absolute"):
        output_directory("data/outputs", app_env="production", volume_mount_path=str(tmp_path))


def test_railway_detected_even_if_app_env_is_dev(tmp_path):
    with pytest.raises(OutputStorageConfigurationError, match="absolute"):
        output_directory("data/outputs", app_env="dev", on_railway=True,
                         volume_mount_path=str(tmp_path))


def test_production_without_volume_is_rejected(tmp_path):
    with pytest.raises(OutputStorageConfigurationError, match="RAILWAY_VOLUME"):
        output_directory(str(tmp_path / "outputs"), app_env="prod")


def test_production_valid_volume_subdirectory(tmp_path):
    assert output_directory(str(tmp_path / "outputs"), app_env="prod",
                            volume_mount_path=str(tmp_path)) == tmp_path / "outputs"


def test_production_cannot_use_volume_root_itself(tmp_path):
    with pytest.raises(OutputStorageConfigurationError, match="subdirectory"):
        output_directory(str(tmp_path), app_env="production",
                         volume_mount_path=str(tmp_path))


def test_production_cannot_write_outside_mount(tmp_path):
    volume = tmp_path / "volume"
    volume.mkdir()
    with pytest.raises(OutputStorageConfigurationError, match="subdirectory"):
        output_directory(str(tmp_path / "other"), app_env="production",
                         volume_mount_path=str(volume))


def test_production_cannot_use_filesystem_root_as_declared_volume():
    filesystem_root = Path(Path.cwd().anchor)
    with pytest.raises(OutputStorageConfigurationError, match="filesystem root"):
        output_directory(
            str(filesystem_root / "generated_outputs"),
            app_env="production",
            volume_mount_path=str(filesystem_root),
        )


def test_production_missing_mount_is_rejected(tmp_path):
    with pytest.raises(OutputStorageConfigurationError, match="missing"):
        output_directory(str(tmp_path / "missing" / "outputs"), app_env="prod",
                         volume_mount_path=str(tmp_path / "missing"))


def test_production_symlink_escape_is_rejected(tmp_path):
    vol = tmp_path / "volume"
    vol.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    (vol / "escape").symlink_to(other, target_is_directory=True)
    with pytest.raises(OutputStorageConfigurationError, match="subdirectory"):
        output_directory(str(vol / "escape" / "outputs"), app_env="prod",
                         volume_mount_path=str(vol))


def test_relative_declared_volume_rejected(tmp_path):
    with pytest.raises(OutputStorageConfigurationError, match="absolute"):
        output_directory(str(tmp_path / "out"), app_env="prod",
                         volume_mount_path="relative/mount")


def test_empty_config_rejected(tmp_path):
    with pytest.raises(OutputStorageConfigurationError, match="empty"):
        output_directory("   ", app_env="dev")


def test_two_renders_never_share_directory(tmp_path):
    first = allocate_export_directory(tmp_path, "test-run")
    second = allocate_export_directory(tmp_path, "test-run")
    assert first != second
    assert first.is_dir() and second.is_dir()
    first.joinpath("lesson.docx").write_bytes(b"previous")
    assert first.joinpath("lesson.docx").read_bytes() == b"previous"


def test_current_directory_reads_railway_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "service-test")
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(tmp_path))
    config = SimpleNamespace(output_storage_dir=str(tmp_path / "out"), app_env="dev")
    assert current_output_directory(config) == tmp_path / "out"


def test_current_directory_fail_closed_without_mount(tmp_path, monkeypatch):
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "service-test")
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)
    config = SimpleNamespace(output_storage_dir=str(tmp_path / "out"), app_env="dev")
    with pytest.raises(OutputStorageConfigurationError, match="RAILWAY_VOLUME"):
        current_output_directory(config)
