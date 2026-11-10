"""Regression tests: exporting the same title must never replace an earlier export."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import output_service


class FakeSession:
    def __init__(self):
        self.rows = []
        self.flush_count = 0
        self.commit_count = 0

    def add(self, row):
        self.rows.append(row)

    async def flush(self):
        self.flush_count += 1

    async def commit(self):
        self.commit_count += 1


@pytest.mark.asyncio
@pytest.mark.parametrize("run_backed", [False, True])
async def test_repeated_render_preserves_prior_export(tmp_path, monkeypatch, run_backed):
    monkeypatch.setattr(
        output_service,
        "settings",
        SimpleNamespace(output_storage_dir=str(tmp_path), output_keep_intermediate_docx_for_pdf=True),
    )
    monkeypatch.setattr(
        output_service.OutputTemplateRegistry,
        "get",
        lambda name: SimpleNamespace(name=name, version="1", font_name="Liberation Sans"),
    )

    render_calls = []

    def write_docx(self, artifact, audience, path):
        path = Path(path)
        path.write_bytes(f"version-{len(render_calls)}".encode())
        render_calls.append(path)

    monkeypatch.setattr(output_service.DocxArtifactRenderer, "render", write_docx)

    session = FakeSession()
    run_id = __import__("uuid").uuid4()
    run = SimpleNamespace(
        id=run_id,
        task_type="lesson",
        output_json={"teacher": {"title": "Repeated title"}},
    )
    async def scalar(_query):
        return run
    session.scalar = scalar

    request = SimpleNamespace(
        generation_run_id=run_id if run_backed else None,
        artifact=None if run_backed else {"title": "Repeated title"},
        artifact_type=None if run_backed else "lesson",
        audience="teacher",
        formats=["docx"],
        template_name="school_clean",
        filename_base=None,
    )
    first = await output_service.OutputService().render(session, request)
    first_path = Path(first["files"][0]["file_path"])
    first_bytes = first_path.read_bytes()

    second = await output_service.OutputService().render(session, request)
    second_path = Path(second["files"][0]["file_path"])

    assert first_path != second_path
    assert first_path.exists() and second_path.exists()
    assert first_path.read_bytes() == first_bytes == b"version-0"
    assert second_path.read_bytes() == b"version-1"
    assert first["files"][0]["sha256"] != second["files"][0]["sha256"]
    assert first["files"][0]["download_path"] != second["files"][0]["download_path"]
    assert session.flush_count == session.commit_count == 2
    assert len(session.rows) == 2
