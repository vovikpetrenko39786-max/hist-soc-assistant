"""No database access: audit row classification with fakes."""
from hashlib import sha256
from types import SimpleNamespace

from scripts.audit_generated_exports import classify_export


def row(path, data):
    return SimpleNamespace(file_path=str(path), size_bytes=len(data), sha256=sha256(data).hexdigest())


def test_audit_healthy_file(tmp_path):
    target = tmp_path / "good.pdf"
    target.write_bytes(b"pdf")
    assert classify_export(row(target, b"pdf"), tmp_path) == "healthy"


def test_audit_unavailable_file(tmp_path):
    assert classify_export(row(tmp_path / "missing.pdf", b"pdf"), tmp_path) == "missing"


def test_audit_outside_root(tmp_path):
    target = tmp_path / "file.docx"
    target.write_bytes(b"docx")
    root = tmp_path / "output"
    root.mkdir()
    assert classify_export(row(target, b"docx"), root) == "outside_storage_root"


def test_audit_detects_corruption_without_leaking_paths(tmp_path):
    target = tmp_path / "corrupt.pdf"
    target.write_bytes(b"different")
    fake = row(target, b"original!")
    assert classify_export(fake, tmp_path) == "hash_mismatch"
