import hashlib

import pytest

from app.services.export_integrity import ExportIntegrityError, verified_export_path


def test_valid_export(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    doc = root / "lesson.docx"
    doc.write_bytes(b"test document")
    result = verified_export_path(
        str(doc), storage_dir=str(root), file_format="docx",
        expected_size=doc.stat().st_size,
        expected_sha256=hashlib.sha256(doc.read_bytes()).hexdigest(),
    )
    assert result == doc


@pytest.mark.parametrize("reason", ["outside", "symlink", "wrong_extension", "wrong_size", "wrong_hash", "missing"])
def test_rejects_unsafe_or_modified_export(tmp_path, reason):
    root = tmp_path / "outputs"
    root.mkdir()
    doc = root / "lesson.docx"
    doc.write_bytes(b"test document")
    target = doc
    size = doc.stat().st_size
    digest = hashlib.sha256(doc.read_bytes()).hexdigest()
    if reason == "outside":
        target = tmp_path / "private.docx"
        target.write_bytes(b"test document")
    elif reason == "symlink":
        outside = tmp_path / "private.docx"
        outside.write_bytes(b"test document")
        target = root / "link.docx"
        target.symlink_to(outside)
    elif reason == "wrong_extension":
        target = root / "lesson.pdf"
        target.write_bytes(b"test document")
    elif reason == "wrong_size":
        size += 1
    elif reason == "wrong_hash":
        digest = "0" * 64
    elif reason == "missing":
        target.unlink()
    with pytest.raises(ExportIntegrityError):
        verified_export_path(
            str(target), storage_dir=str(root), file_format="docx",
            expected_size=size, expected_sha256=digest,
        )
