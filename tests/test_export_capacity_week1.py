"""Export reserve protects source books from a full persistent volume."""
from collections import namedtuple

import pytest

from app.services.output_storage_guard import (
    OutputStorageConfigurationError,
    require_free_export_space,
)

Usage = namedtuple("Usage", "total used free")
MB = 1024 * 1024


def quota(free):
    return lambda path: Usage(total=450 * MB, used=450 * MB-free, free=free)


def test_rejects_low_space_without_creating_directories(tmp_path):
    output = tmp_path / "new" / "nested"
    with pytest.raises(OutputStorageConfigurationError, match="Not enough free space"):
        require_free_export_space(output, disk_usage=quota(32 * MB))
    assert not output.exists()


def test_allows_at_or_above_reserved_space(tmp_path):
    target = tmp_path / "generated"
    assert require_free_export_space(target, disk_usage=quota(64 * MB)) == 64 * MB
    assert require_free_export_space(target, minimum_free_mb=100,
                                     disk_usage=quota(101 * MB)) == 101 * MB


@pytest.mark.parametrize("invalid", [0, -1, 1025, 2.3, "64", None])
def test_refuses_invalid_threshold(tmp_path, invalid):
    with pytest.raises(OutputStorageConfigurationError, match="Invalid"):
        require_free_export_space(tmp_path, minimum_free_mb=invalid, disk_usage=quota(200 * MB))


def test_usage_failure_is_an_explicit_export_error(tmp_path):
    def unavailable(path):
        raise OSError("internal storage path, not safe to echo")
    with pytest.raises(OutputStorageConfigurationError, match="Cannot verify free space") as exc:
        require_free_export_space(tmp_path, disk_usage=unavailable)
    assert "internal storage path" not in str(exc.value)


def test_uses_nearest_existing_parent(tmp_path):
    seen = []
    def measured(path):
        seen.append(path)
        return Usage(total=200 * MB, used=50 * MB, free=150 * MB)
    assert require_free_export_space(tmp_path / "new" / "exports", disk_usage=measured)
    assert seen == [tmp_path.resolve()]


def test_file_is_not_directory(tmp_path):
    out = tmp_path / "file"
    out.write_text("not a directory")
    with pytest.raises(OutputStorageConfigurationError, match="not a directory"):
        require_free_export_space(out, disk_usage=quota(180 * MB))


def test_invalid_disk_usage_does_not_pass(tmp_path):
    def wrong_usage(path):
        return object()
    with pytest.raises(OutputStorageConfigurationError, match="Cannot verify free space"):
        require_free_export_space(tmp_path, disk_usage=wrong_usage)
