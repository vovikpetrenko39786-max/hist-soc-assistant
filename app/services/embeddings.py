from __future__ import annotations

import hashlib
import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import Source, SourceChunk

settings = get_settings()
_TOKEN_RE = re.compile(r"[\wа-яё]+", re.IGNORECASE | re.UNICODE)


class EmbeddingError(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    name: str
    model: str
    dim: int
    production_quality: bool

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...


def _l2_normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values))
    return values if norm == 0 else [v / norm for v in values]


class HashEmbeddingProvider:
    """Offline deterministic development provider, not a semantic production model."""

    name = "hash"
    production_quality = False

    def __init__(self, dim: int = 384, model: str = "hash-384-v1"):
        self.dim = dim
        self.model = model

    def _embed(self, text: str) -> list[float]:
        tokens = _TOKEN_RE.findall(text.lower())
        features = list(tokens) + [f"{a}::{b}" for a, b in zip(tokens, tokens[1:])]
        vector = [0.0] * self.dim
        for token in features:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:8], "big") % self.dim
            sign = 1.0 if digest[8] % 2 == 0 else -1.0
            vector[index] += sign
        return _l2_normalize(vector)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class HttpEmbeddingProvider:
    """Production adapter for a compatible /embeddings HTTP endpoint."""

    name = "http"
    production_quality = True

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        dim: int,
        timeout_seconds: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dim = dim
        self.timeout_seconds = timeout_seconds

    async def _call(self, texts: list[str]) -> list[list[float]]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json={"model": self.model, "input": texts},
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise EmbeddingError(
                    f"Embedding endpoint returned {response.status_code}: {response.text[:500]}"
                ) from exc
            payload = response.json()

        rows = payload.get("data")
        if not isinstance(rows, list) or len(rows) != len(texts):
            raise EmbeddingError("Unexpected embedding response shape")
        rows = sorted(rows, key=lambda row: row.get("index", 0))
        vectors = [row.get("embedding") for row in rows]
        if any(not isinstance(v, list) for v in vectors):
            raise EmbeddingError("Embedding response has no vector data")
        for vector in vectors:
            if len(vector) != self.dim:
                raise EmbeddingError(
                    f"Embedding dimension mismatch: expected {self.dim}, got {len(vector)}"
                )
        return vectors

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._call(texts)

    async def embed_query(self, text: str) -> list[float]:
        return (await self._call([text]))[0]


def get_embedding_provider() -> EmbeddingProvider:
    provider = settings.embedding_provider.lower().strip()
    if provider == "hash":
        return HashEmbeddingProvider(settings.embedding_dim, settings.embedding_model)
    if provider == "http":
        if not settings.embedding_http_base_url:
            raise EmbeddingError("EMBEDDING_HTTP_BASE_URL is required for provider=http")
        return HttpEmbeddingProvider(
            base_url=settings.embedding_http_base_url,
            api_key=settings.embedding_http_api_key or settings.openai_api_key,
            model=settings.embedding_http_model or settings.embedding_model,
            dim=settings.embedding_dim,
            timeout_seconds=settings.embedding_http_timeout_seconds,
        )
    raise EmbeddingError(f"Unsupported embedding provider: {settings.embedding_provider}")


@dataclass
class EmbeddingRunResult:
    source_id: str
    source_key: str | None
    provider: str
    model: str
    dim: int
    chunks_total: int
    chunks_embedded: int
    chunks_ready: int
    source_status: str
    production_quality: bool


class EmbeddingService:
    async def embed_source(
        self,
        session: AsyncSession,
        source_id: uuid.UUID,
        force: bool = False,
    ) -> dict:
        source = await session.scalar(select(Source).where(Source.id == source_id))
        if source is None:
            raise EmbeddingError("Source not found")
        if source.ingestion_status in {"needs_ocr", "failed", None}:
            raise EmbeddingError(
                f"Source is not ready for embeddings: ingestion_status={source.ingestion_status}"
            )

        provider = get_embedding_provider()
        stmt = select(SourceChunk).where(SourceChunk.source_id == source_id).order_by(SourceChunk.chunk_index)
        if not force:
            stmt = stmt.where(SourceChunk.embedding_status != "ready")
        chunks = list((await session.execute(stmt)).scalars().all())

        total = await session.scalar(
            select(func.count(SourceChunk.id)).where(SourceChunk.source_id == source_id)
        ) or 0

        embedded_count = 0
        batch_size = max(1, settings.embedding_batch_size)
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            vectors = await provider.embed_documents([chunk.text for chunk in batch])
            if len(vectors) != len(batch):
                raise EmbeddingError("Embedding provider returned wrong batch size")
            now = datetime.now(timezone.utc)
            for chunk, vector in zip(batch, vectors):
                if len(vector) != provider.dim:
                    raise EmbeddingError(f"Embedding dimension mismatch for chunk {chunk.id}")
                chunk.embedding = vector
                chunk.embedding_status = "ready"
                chunk.embedding_model = provider.model
                chunk.embedding_dim = provider.dim
                chunk.embedded_at = now
                embedded_count += 1

        await session.flush()
        ready_count = await session.scalar(
            select(func.count(SourceChunk.id)).where(
                SourceChunk.source_id == source_id,
                SourceChunk.embedding_status == "ready",
            )
        ) or 0

        if total and ready_count == total:
            source.availability_status = "rag_ready" if provider.production_quality else "rag_ready_dev"
            source.ingestion_status = "rag_ready" if provider.production_quality else "rag_ready_dev"
        else:
            source.availability_status = "embedding_partial"
            source.ingestion_status = "embedding_partial"

        source.metadata_json = {
            **(source.metadata_json or {}),
            "embedding_provider": provider.name,
            "embedding_model": provider.model,
            "embedding_dim": provider.dim,
            "embedding_production_quality": provider.production_quality,
        }
        await session.commit()

        return EmbeddingRunResult(
            source_id=str(source.id),
            source_key=source.source_key,
            provider=provider.name,
            model=provider.model,
            dim=provider.dim,
            chunks_total=int(total),
            chunks_embedded=embedded_count,
            chunks_ready=int(ready_count),
            source_status=source.ingestion_status or "unknown",
            production_quality=provider.production_quality,
        ).__dict__
