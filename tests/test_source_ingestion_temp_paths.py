import io
from types import SimpleNamespace
import uuid

import pytest
from fastapi import UploadFile

from app.services.source_ingestion import SourceIngestionService


class SourceOnlySession:
    def __init__(self, source):
        self.source = source

    async def scalar(self, _statement):
        return self.source


@pytest.mark.asyncio
async def test_parallel_attempts_receive_distinct_temporary_paths(tmp_path, monkeypatch):
    source = SimpleNamespace(id=uuid.uuid4(), file_hash=None, file_path=None)
    service = SourceIngestionService()
    service.settings = SimpleNamespace(source_storage_dir=str(tmp_path))
    observed = []

    async def capture_and_stop(_upload, path):
        observed.append(path)
        path.write_bytes(b"partial")
        raise RuntimeError("synthetic upload interruption")

    monkeypatch.setattr(service, "_save_upload", capture_and_stop)

    for index in range(2):
        upload = UploadFile(
            filename=f"attempt-{index}.pdf",
            file=io.BytesIO(b"pdf"),
        )
        with pytest.raises(RuntimeError, match="synthetic upload interruption"):
            await service.ingest_pdf(SourceOnlySession(source), source.id, upload)

    assert len(set(observed)) == 2
    assert all(path.name.startswith(".upload-") for path in observed)
    assert all(not path.exists() for path in observed)
