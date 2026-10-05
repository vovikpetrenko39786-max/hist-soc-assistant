from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx


class BackendClientError(RuntimeError):
    pass


class TeacherAssistantApi:
    def __init__(self, base_url: str, timeout_seconds: float = 240.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(f"{self.base_url}/api/v1/pilot/health")
            response.raise_for_status()
            return response.json()

    async def assistant(self, message: str, user_context: dict) -> dict:
        payload = {
            "message": message,
            "auto_render": True,
            "allow_web_fallback": True,
            "default_formats": ["docx"],
            "client_context": user_context,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/assistant",
                json=payload,
            )
            if response.status_code >= 400:
                raise BackendClientError(
                    f"Backend {response.status_code}: {response.text[:800]}"
                )
            return response.json()

    async def feedback(self, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/pilot/feedback",
                json=payload,
            )
            if response.status_code >= 400:
                raise BackendClientError(
                    f"Feedback backend {response.status_code}: {response.text[:500]}"
                )
            return response.json()

    async def download(self, download_path: str, file_name: str) -> Path:
        url = (
            download_path
            if download_path.startswith("http")
            else f"{self.base_url}{download_path}"
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            if response.status_code >= 400:
                raise BackendClientError(
                    f"Download {response.status_code}: {response.text[:500]}"
                )
            suffix = Path(file_name).suffix
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(response.content)
                return Path(tmp.name)
