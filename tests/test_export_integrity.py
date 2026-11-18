import hashlib

import pytest

from app.services.export_integrity import ExportIntegrityError, verified_export_path


def test_valid_export(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    document = root / "lesson.docx"
    document.write_bytes(b"test document")

    result = verified_export_path(
        str(document),
        str(root),
        document.stat().st_size,
        hashlib.sha256(document.read_bytes()).hexdigest(),
        file_format="docx",
    )

    assert result == document


@pytest.mark.parametrize(
    "reason",
    ["outside", "symlink", "wrong_extension", "wrong_size", "wrong_hash", "missing"],
)
def test_rejects_unsafe_or_modified_export(tmp_path, reason):
    root = tmp_path / "outputs"
    root.mkdir()
    document = root / "lesson.docx"
    document.write_bytes(b"test document")
    target = document
    size = document.stat().st_size
    digest = hashlib.sha256(document.read_bytes()).hexdigest()

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
            str(target),
            str(root),
            size,
            digest,
            file_format="docx",
        )


def test_rejects_filesystem_root_as_storage(tmp_path):
    document = tmp_path / "lesson.docx"
    document.write_bytes(b"test")

    with pytest.raises(ExportIntegrityError, match="invalid_root"):
        verified_export_path(
            str(document),
            document.anchor,
            4,
            hashlib.sha256(b"test").hexdigest(),
            file_format="docx",
        )
