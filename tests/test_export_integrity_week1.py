"""Unit tests for export integrity and path containment."""
from hashlib import sha256

import pytest

from app.services.export_integrity import (
    ExportIntegrityError,
    storage_roots,
    verified_export_path,
    verified_export_path_in_roots,
)


def test_valid_export(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    file = root / "lesson.docx"
    file.write_bytes(b"real contents")
    assert verified_export_path(str(file), str(root), 13, sha256(b"real contents").hexdigest()) == file


def test_missing_export(tmp_path):
    with pytest.raises(ExportIntegrityError, match="missing"):
        verified_export_path(str(tmp_path / "missing.docx"), str(tmp_path), 5, "x" * 64)


def test_traversal_or_external_path_is_rejected(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    outside = tmp_path / "private.docx"
    outside.write_bytes(b"secret")
    with pytest.raises(ExportIntegrityError, match="outside_root"):
        verified_export_path(str(outside), str(root), 6, sha256(b"secret").hexdigest())


def test_symlink_to_outside_is_rejected(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    outside = tmp_path / "private.docx"
    outside.write_bytes(b"secret")
    (root / "linked.docx").symlink_to(outside)
    with pytest.raises(ExportIntegrityError, match="outside_root"):
        verified_export_path(str(root / "linked.docx"), str(root), 6, sha256(b"secret").hexdigest())


def test_changed_size_is_rejected(tmp_path):
    file = tmp_path / "lesson.docx"
    file.write_bytes(b"contents")
    with pytest.raises(ExportIntegrityError, match="corrupt"):
        verified_export_path(str(file), str(tmp_path), 99, sha256(b"contents").hexdigest())


def test_changed_bytes_of_same_size_are_rejected(tmp_path):
    file = tmp_path / "lesson.docx"
    file.write_bytes(b"changed!")
    with pytest.raises(ExportIntegrityError, match="corrupt"):
        verified_export_path(str(file), str(tmp_path), 8, sha256(b"original").hexdigest())


def test_verified_legacy_root_preserves_old_document(tmp_path):
    current = tmp_path / "current"
    legacy = tmp_path / "legacy"
    current.mkdir()
    legacy.mkdir()
    file = legacy / "old.docx"
    file.write_bytes(b"old-but-valid")
    roots = storage_roots(str(current), f'["{legacy}"]')
    assert verified_export_path_in_roots(
        str(file), roots, len(b"old-but-valid"), sha256(b"old-but-valid").hexdigest()
    ) == file


@pytest.mark.parametrize("raw", ['"/tmp"', '["relative"]', '["/"]'])
def test_unsafe_legacy_root_configuration_is_rejected(tmp_path, raw):
    with pytest.raises(ExportIntegrityError, match="invalid_roots"):
        storage_roots(str(tmp_path), raw)
