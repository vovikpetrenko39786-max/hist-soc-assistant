from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx


class BackendClientError(RuntimeError):
    pass


class TeacherAssistantApi:
    def __init__(self, base_url: str, timeout_seconds: float = 240.0, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds
        self.headers = {"X-Pilot-Key": api_key} if api_key else {}

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(f"{self.base_url}/api/v1/pilot/health", headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def assistant(self, message: str, user_context: dict,
                        class_course_id: str | None = None,
                        source_key: str | None = None) -> dict:
        payload = {
            "message": message,
            "auto_render": True,
            "allow_web_fallback": True,
            "default_formats": ["docx"],
            "client_context": user_context,
        }
        if class_course_id is not None:
            payload["class_course_id"] = class_course_id
        if source_key is not None:
            payload["source_key"] = source_key
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/assistant",
                json=payload,
                headers=self.headers,
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
                headers=self.headers,
            )
            if response.status_code >= 400:
                raise BackendClientError(
                    f"Feedback backend {response.status_code}: {response.text[:500]}"
                )
            return response.json()

    async def download(self, download_path: str, file_name: str) -> Path:
        if not download_path.startswith("/api/v1/outputs/files/"):
            raise BackendClientError("Unexpected download path")
        url = f"{self.base_url}{download_path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self.headers)
            if response.status_code >= 400:
                raise BackendClientError(
                    f"Download {response.status_code}: {response.text[:500]}"
                )
            suffix = Path(file_name).suffix
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(response.content)
                return Path(tmp.name)
