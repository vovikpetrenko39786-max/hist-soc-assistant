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

    def user_headers(self, user_id: int) -> dict[str, str]:
        if not isinstance(user_id, int) or user_id <= 0:
            raise BackendClientError("A valid pilot user ID is required")
        return {**self.headers, "X-Pilot-User-ID": str(user_id)}

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

    async def assistant(self, message: str, user_context: dict,
                        user_id: int,
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
                headers=self.user_headers(user_id),
            )
            if response.status_code >= 400:
                raise BackendClientError(
                    f"Backend {response.status_code}: {response.text[:800]}"
                )
            return response.json()

    async def feedback(self, payload: dict, user_id: int) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/pilot/feedback",
                json=payload,
                headers=self.user_headers(user_id),
            )
            if response.status_code >= 400:
                raise BackendClientError(
                    f"Feedback backend {response.status_code}: {response.text[:500]}"
                )
            return response.json()

    async def download(self, download_path: str, file_name: str, user_id: int) -> Path:
        if not download_path.startswith("/api/v1/outputs/files/"):
            raise BackendClientError("Unexpected download path")
        url = f"{self.base_url}{download_path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self.user_headers(user_id))
            if response.status_code >= 400:
                raise BackendClientError(
                    f"Download {response.status_code}: {response.text[:500]}"
                )
            suffix = Path(file_name).suffix
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(response.content)
                return Path(tmp.name)
