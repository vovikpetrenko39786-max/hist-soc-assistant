from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.catalog import TopicSource
from app.models.entities import Source, SourceChunk
from app.schemas.retrieval import RetrievalRequest
from app.services.embeddings import EmbeddingError, get_embedding_provider

settings = get_settings()
_TOKEN_RE = re.compile(r"[\wа-яё]+", re.IGNORECASE | re.UNICODE)
_STATUS_PRIORITY = {
    "official": 1.00, "primary": 0.96, "exam": 0.94,
    "secondary": 0.80, "methodical": 0.74, "reference": 0.68, "archive": 0.10,
}


@dataclass
class Candidate:
    chunk: SourceChunk
    source: Source
    lexical_score: float | None = None
    vector_similarity: float | None = None
    lexical_rank: int | None = None
    vector_rank: int | None = None
    topic_priority: int | None = None
    exact_match: bool = False
    final_score: float = 0.0


class RetrievalError(RuntimeError):
    pass


class RetrievalService:
    async def retrieve(self, session: AsyncSession, request: RetrievalRequest) -> dict:
        source_ids, topic_priorities = await self._resolve_source_scope(session, request)
        warnings: list[str] = []
        lexical_rows = []
        vector_rows = []

        if request.mode in {"lexical", "hybrid", "exact"}:
            lexical_rows = await self._lexical_candidates(session, request, source_ids)

        if request.mode in {"vector", "hybrid"}:
            try:
                vector_rows = await self._vector_candidates(session, request, source_ids)
                if not vector_rows:
                    warnings.append(
                        "Vector branch returned no ready embeddings; results may rely on lexical search."
                    )
            except EmbeddingError as exc:
                warnings.append(f"Vector search unavailable: {exc}")

        candidates: dict[uuid.UUID, Candidate] = {}
        for rank, (chunk, source, raw_score) in enumerate(lexical_rows, start=1):
            candidate = candidates.setdefault(
                chunk.id,
                Candidate(chunk=chunk, source=source, topic_priority=topic_priorities.get(source.id)),
            )
            candidate.lexical_score = float(raw_score)
            candidate.lexical_rank = rank

        for rank, (chunk, source, similarity) in enumerate(vector_rows, start=1):
            candidate = candidates.setdefault(
                chunk.id,
                Candidate(chunk=chunk, source=source, topic_priority=topic_priorities.get(source.id)),
            )
            candidate.vector_similarity = float(similarity)
            candidate.vector_rank = rank

        phrase = (request.exact_phrase or "").strip().casefold()
        query = request.query.casefold()
        for candidate in candidates.values():
            text = candidate.chunk.text.casefold()
            candidate.exact_match = bool(
                (phrase and phrase in text) or (not phrase and query in text)
            )
            candidate.final_score = self._final_score(candidate, request)

        ordered = sorted(
            candidates.values(),
            key=lambda item: (item.final_score, item.exact_match),
            reverse=True,
        )[:request.top_k]

        if request.mode == "exact" and not ordered:
            warnings.append("Exact phrase was not found in the selected source scope.")

        if request.strict_source and ordered:
            if any(
                (request.source_id and item.source.id != request.source_id)
                or (request.source_key and item.source.source_key != request.source_key)
                for item in ordered
            ):
                raise RetrievalError("Strict-source invariant violated")

        return {
            "query": request.query,
            "mode": request.mode,
            "strict_source": request.strict_source,
            "hits": [self._serialize_hit(item, request) for item in ordered],
            "warnings": warnings,
        }

    async def _resolve_source_scope(self, session, request):
        allowed = None
        priorities: dict[uuid.UUID, int] = {}

        if request.topic_id:
            rows = (await session.execute(
                select(TopicSource.source_id, TopicSource.priority).where(
                    TopicSource.topic_id == request.topic_id
                )
            )).all()
            allowed = {row.source_id for row in rows}
            priorities = {row.source_id: row.priority for row in rows}

        explicit: set[uuid.UUID] = set()
        if request.source_id:
            explicit.add(request.source_id)
        if request.source_key:
            source_id = await session.scalar(
                select(Source.id).where(Source.source_key == request.source_key)
            )
            if source_id is None:
                raise RetrievalError(f"Unknown source_key: {request.source_key}")
            explicit.add(source_id)

        if explicit:
            allowed = explicit if allowed is None else allowed.intersection(explicit)

        if request.strict_source and not allowed:
            raise RetrievalError("Strict source scope resolved to zero sources")
        return allowed, priorities

    @staticmethod
    def _base_filters(request, source_ids):
        filters = []
        if source_ids is not None:
            filters.append(Source.id.in_(source_ids))
        if request.subject:
            filters.append(Source.subject == request.subject)
        if request.grade is not None:
            filters.append(or_(Source.grade == request.grade, Source.grade.is_(None)))
        if request.level:
            filters.append(or_(Source.level == request.level, Source.level.is_(None)))
        if request.source_statuses:
            filters.append(Source.status.in_(request.source_statuses))
        if not request.include_archived:
            filters.append(Source.is_current.is_(True))
        return filters

    async def _lexical_candidates(self, session, request, source_ids):
        filters = self._base_filters(request, source_ids)
        candidate_k = max(request.candidate_k, request.top_k)
        exact_phrase = (request.exact_phrase or "").strip()

        if request.mode == "exact" or exact_phrase:
            needle = exact_phrase or request.query
            stmt = (
                select(SourceChunk, Source)
                .join(Source, SourceChunk.source_id == Source.id)
                .where(*filters, SourceChunk.text.ilike(f"%{needle}%"))
                .order_by(desc(Source.authority_rank), SourceChunk.chunk_index)
                .limit(candidate_k)
            )
            return [
                (chunk, source, 1.0)
                for chunk, source in (await session.execute(stmt)).all()
            ]

        ts_query = func.websearch_to_tsquery(settings.retrieval_language_config, request.query)
        text_vector = func.to_tsvector(settings.retrieval_language_config, SourceChunk.text)
        rank_expr = func.ts_rank_cd(text_vector, ts_query)
        stmt = (
            select(SourceChunk, Source, rank_expr.label("lexical_score"))
            .join(Source, SourceChunk.source_id == Source.id)
            .where(*filters, text_vector.op("@@")(ts_query))
            .order_by(desc("lexical_score"), desc(Source.authority_rank))
            .limit(candidate_k)
        )
        return [
            (chunk, source, float(score or 0.0))
            for chunk, source, score in (await session.execute(stmt)).all()
        ]

    async def _vector_candidates(self, session, request, source_ids):
        provider = get_embedding_provider()
        query_vector = await provider.embed_query(request.query)
        filters = self._base_filters(request, source_ids) + [
            SourceChunk.embedding_status == "ready",
            SourceChunk.embedding_dim == provider.dim,
            SourceChunk.embedding_model == provider.model,
            SourceChunk.embedding.is_not(None),
        ]
        distance = SourceChunk.embedding.cosine_distance(query_vector)
        stmt = (
            select(SourceChunk, Source, distance.label("distance"))
            .join(Source, SourceChunk.source_id == Source.id)
            .where(*filters)
            .order_by(distance.asc(), desc(Source.authority_rank))
            .limit(max(request.candidate_k, request.top_k))
        )
        rows = (await session.execute(stmt)).all()
        return [
            (chunk, source, max(-1.0, min(1.0, 1.0 - float(distance_value))))
            for chunk, source, distance_value in rows
        ]

    @staticmethod
    def _rank_value(rank):
        return 0.0 if rank is None else 1.0 / rank

    @classmethod
    def _final_score(cls, candidate, request):
        lexical = cls._rank_value(candidate.lexical_rank)
        vector = cls._rank_value(candidate.vector_rank)
        authority = max(0.0, min(1.0, candidate.source.authority_rank / 100.0))
        status = _STATUS_PRIORITY.get(candidate.source.status, 0.5)
        current = 1.0 if candidate.source.is_current else 0.0
        topic = 0.0 if candidate.topic_priority is None else 1.0 / max(1, candidate.topic_priority)
        exact = 1.0 if candidate.exact_match else 0.0

        if request.mode == "exact":
            score = .65*exact + .15*authority + .10*status + .05*current + .05*topic
        elif request.mode == "lexical":
            score = .68*lexical + .10*authority + .08*status + .04*current + .05*exact + .05*topic
        elif request.mode == "vector":
            score = .68*vector + .10*authority + .08*status + .04*current + .05*exact + .05*topic
        else:
            score = .40*lexical + .32*vector + .08*authority + .06*status + .04*current + .05*exact + .05*topic
        return round(max(0.0, min(1.0, score)), 6)

    @staticmethod
    def _snippet(text, query, exact_phrase=None, max_chars=520):
        if not text:
            return ""
        needle = (exact_phrase or query).strip()
        low = text.casefold()
        pos = low.find(needle.casefold()) if needle else -1
        if pos < 0:
            tokens = _TOKEN_RE.findall(query.casefold())
            found = [low.find(t) for t in tokens if low.find(t) >= 0]
            pos = min(found) if found else 0
        half = max_chars // 2
        start = max(0, pos - half)
        end = min(len(text), start + max_chars)
        if end - start < max_chars and start > 0:
            start = max(0, end - max_chars)
        snippet = text[start:end].strip()
        return ("…" if start > 0 else "") + snippet + ("…" if end < len(text) else "")

    @staticmethod
    def _page_reference_status(chunk):
        if chunk.page_print is not None:
            return "verified_print_and_pdf"
        if chunk.page_pdf is not None:
            return "verified_pdf_only"
        return "page_unknown"

    def _serialize_hit(self, candidate, request):
        chunk, source = candidate.chunk, candidate.source
        return {
            "chunk_id": chunk.id,
            "source_id": source.id,
            "source_key": source.source_key,
            "source_title": source.title,
            "source_type": source.source_type,
            "source_status": source.status,
            "origin": source.origin,
            "authority_rank": source.authority_rank,
            "is_current": source.is_current,
            "section": chunk.section,
            "page_pdf_start": chunk.page_pdf,
            "page_pdf_end": chunk.page_pdf_end,
            "page_print_start": chunk.page_print,
            "page_print_end": chunk.page_print_end,
            "snippet": self._snippet(chunk.text, request.query, request.exact_phrase),
            "exact_match": candidate.exact_match,
            "quote_safe": bool(request.exact_phrase and candidate.exact_match),
            "lexical_rank": candidate.lexical_rank,
            "vector_rank": candidate.vector_rank,
            "lexical_score": candidate.lexical_score,
            "vector_similarity": candidate.vector_similarity,
            "final_score": candidate.final_score,
            "embedding_model": chunk.embedding_model,
            "page_reference_status": self._page_reference_status(chunk),
        }
