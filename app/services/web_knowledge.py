from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import WebSearchRun

settings = get_settings()


class WebKnowledgeError(RuntimeError):
    pass


class OfficialDomainPolicy:
    EDUCATION = [
        "edsoo.ru",
        "edu.gov.ru",
        "minobrnauki.gov.ru",
    ]
    EXAMS = [
        "fipi.ru",
        "doc.fipi.ru",
    ]
    LAW = [
        "publication.pravo.gov.ru",
        "pravo.gov.ru",
        "kremlin.ru",
        "government.ru",
    ]
    STATISTICS = [
        "rosstat.gov.ru",
    ]

    @classmethod
    def allowed_domains(cls, query: str, subject: str | None = None) -> list[str]:
        q = query.casefold()
        domains: list[str] = []

        if any(x in q for x in (
            "егэ", "огэ", "фипи", "ким", "демовер", "кодификатор",
            "спецификац", "экзамен",
        )):
            domains += cls.EXAMS

        if any(x in q for x in (
            "фгос", "фоп", "фрп", "едсоо", "рабочая программа",
            "федеральная программа", "учебная программа",
        )):
            domains += cls.EDUCATION

        if any(x in q for x in (
            "закон", "право", "правовая", "правовой", "конституц",
            "кодекс", "статья", "федеральный закон", "норматив",
        )):
            domains += cls.LAW

        if any(x in q for x in (
            "статистик", "данные", "уровень безработицы", "инфляц",
            "население", "ввп",
        )):
            domains += cls.STATISTICS

        # History/social-studies teacher fallback should start with authoritative
        # education/exam sources even when the query classifier is uncertain.
        if not domains:
            domains += cls.EDUCATION + cls.EXAMS

        # Stable order, no duplicates.
        return list(dict.fromkeys(domains))


class OpenAIResponsesWebSearchClient:
    provider = "openai"

    def __init__(self):
        self.base_url = settings.openai_responses_base_url.rstrip("/")
        self.api_key = settings.openai_api_key
        self.model = settings.web_search_model

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _extract_response(payload: dict) -> tuple[str, list[dict], list[dict]]:
        text_parts: list[str] = []
        citations: list[dict] = []
        sources: list[dict] = []

        for item in payload.get("output", []) or []:
            if item.get("type") == "message":
                for content in item.get("content", []) or []:
                    if content.get("type") == "output_text":
                        text = content.get("text")
                        if text:
                            text_parts.append(text)
                        for ann in content.get("annotations", []) or []:
                            if ann.get("type") == "url_citation":
                                citation = {
                                    "url": ann.get("url"),
                                    "title": ann.get("title"),
                                    "start_index": ann.get("start_index"),
                                    "end_index": ann.get("end_index"),
                                }
                                citations.append(citation)

            if item.get("type") == "web_search_call":
                action = item.get("action") or {}
                for src in action.get("sources", []) or []:
                    if isinstance(src, str):
                        sources.append({"url": src})
                    elif isinstance(src, dict):
                        sources.append({
                            "url": src.get("url"),
                            "title": src.get("title"),
                            "type": src.get("type"),
                        })

        # Some compatible endpoints expose output_text convenience data.
        if not text_parts and payload.get("output_text"):
            text_parts.append(str(payload["output_text"]))

        # Citation URLs are also trustworthy evidence when complete sources were
        # not returned by a compatible endpoint.
        for citation in citations:
            if citation.get("url"):
                sources.append({
                    "url": citation["url"],
                    "title": citation.get("title"),
                })

        dedup: dict[str, dict] = {}
        for src in sources:
            url = src.get("url")
            if not url:
                continue
            domain = urlparse(url).netloc.lower()
            dedup[url] = {
                "url": url,
                "title": src.get("title"),
                "domain": domain,
                "source_type": "web",
            }

        return "\n".join(text_parts).strip(), list(dedup.values()), citations

    async def search(
        self,
        query: str,
        *,
        allowed_domains: list[str] | None,
        force_search: bool = True,
    ) -> dict:
        if not self.api_key:
            raise WebKnowledgeError(
                "OPENAI_API_KEY is not configured; web search is unavailable."
            )

        tool: dict = {
            "type": "web_search",
            "search_context_size": settings.web_search_context_size,
        }
        if allowed_domains:
            tool["filters"] = {"allowed_domains": allowed_domains}

        request_json = {
            "model": self.model,
            "tools": [tool],
            "tool_choice": "required" if force_search else "auto",
            "include": ["web_search_call.action.sources"],
            "input": query,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=settings.web_search_timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/responses",
                headers=headers,
                json=request_json,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise WebKnowledgeError(
                    f"OpenAI Responses API returned {response.status_code}: "
                    f"{response.text[:700]}"
                ) from exc

        answer, sources, citations = self._extract_response(response.json())
        return {
            "answer": answer,
            "sources": sources[: settings.web_max_sources],
            "citations": citations,
            "model": self.model,
        }


class WebFallbackPolicy:
    FRESHNESS_MARKERS = (
        "сегодня", "сейчас", "актуаль", "последн", "свеж",
        "2027", "изменения", "действующ", "текущ",
    )

    @classmethod
    def should_search(
        cls,
        *,
        policy: str,
        local_retrieval: dict | None,
        request_text: str,
        allow_web_fallback: bool,
        strict_source: bool,
    ) -> bool:
        if strict_source:
            return False
        if not allow_web_fallback or policy == "library_only":
            return False
        if policy == "official_web_first":
            return True

        hits = (local_retrieval or {}).get("hits", []) or []
        if len(hits) < settings.web_fallback_min_local_hits:
            return True

        q = request_text.casefold()
        return any(marker in q for marker in cls.FRESHNESS_MARKERS)


class WebKnowledgeService:
    def __init__(self):
        self.client = OpenAIResponsesWebSearchClient()

    async def search(
        self,
        session: AsyncSession,
        *,
        query: str,
        policy: str,
        subject: str | None,
        topic_id: uuid.UUID | None = None,
        scope: str = "official",
        force_search: bool = True,
        save_run: bool = True,
    ) -> dict:
        allowed_domains = (
            OfficialDomainPolicy.allowed_domains(query, subject)
            if scope == "official"
            else []
        )

        run = None
        if save_run:
            run = WebSearchRun(
                topic_id=topic_id,
                policy=policy,
                scope=scope,
                provider=self.client.provider,
                model=self.client.model,
                query=query,
                allowed_domains=allowed_domains,
                status="running",
            )
            session.add(run)
            await session.flush()

        try:
            result = await self.client.search(
                query,
                allowed_domains=allowed_domains or None,
                force_search=force_search,
            )
            if run:
                run.response_text = result.get("answer")
                run.sources_json = result.get("sources", [])
                run.status = "completed"
                run.completed_at = datetime.now(timezone.utc)
                await session.commit()
            return {
                "performed": True,
                "provider": self.client.provider,
                "model": result.get("model"),
                "policy": policy,
                "scope": scope,
                "query": query,
                "allowed_domains": allowed_domains,
                "answer": result.get("answer"),
                "sources": result.get("sources", []),
                "citations": result.get("citations", []),
                "search_run_id": str(run.id) if run else None,
                "warnings": [],
            }
        except WebKnowledgeError as exc:
            if run:
                run.status = "failed"
                run.error_message = str(exc)
                run.completed_at = datetime.now(timezone.utc)
                await session.commit()
            return {
                "performed": False,
                "provider": self.client.provider,
                "model": self.client.model,
                "policy": policy,
                "scope": scope,
                "query": query,
                "allowed_domains": allowed_domains,
                "answer": None,
                "sources": [],
                "citations": [],
                "search_run_id": str(run.id) if run else None,
                "warnings": [str(exc)],
            }

    async def controlled_fallback(
        self,
        session: AsyncSession,
        *,
        query: str,
        policy: str,
        subject: str | None,
        topic_id: uuid.UUID | None,
        local_retrieval: dict | None,
        request_text: str,
        allow_web_fallback: bool,
        strict_source: bool,
        dry_run: bool,
        save_run: bool,
    ) -> dict:
        should = WebFallbackPolicy.should_search(
            policy=policy,
            local_retrieval=local_retrieval,
            request_text=request_text,
            allow_web_fallback=allow_web_fallback,
            strict_source=strict_source,
        )

        if not should:
            return {
                "performed": False,
                "planned": False,
                "provider": self.client.provider,
                "model": self.client.model,
                "policy": policy,
                "scope": "none",
                "query": query,
                "allowed_domains": [],
                "answer": None,
                "sources": [],
                "citations": [],
                "search_run_id": None,
                "warnings": [],
            }

        if dry_run:
            domains = OfficialDomainPolicy.allowed_domains(query, subject)
            return {
                "performed": False,
                "planned": True,
                "provider": self.client.provider,
                "model": self.client.model,
                "policy": policy,
                "scope": "official",
                "query": query,
                "allowed_domains": domains,
                "answer": None,
                "sources": [],
                "citations": [],
                "search_run_id": None,
                "warnings": ["Dry run: external web search was planned but not executed."],
            }

        # Stage 1: official domains.
        official = await self.search(
            session,
            query=query,
            policy=policy,
            subject=subject,
            topic_id=topic_id,
            scope="official",
            force_search=True,
            save_run=save_run,
        )

        # Stage 2: general web only when official search produced no usable source.
        if (
            settings.web_allow_general_after_official
            and allow_web_fallback
            and not strict_source
            and official.get("performed")
            and not official.get("sources")
        ):
            general = await self.search(
                session,
                query=query,
                policy=policy,
                subject=subject,
                topic_id=topic_id,
                scope="general",
                force_search=True,
                save_run=save_run,
            )
            if general.get("performed"):
                general["warnings"] = [
                    "Official-domain search returned no sources; general web fallback was used."
                ] + general.get("warnings", [])
                return general

        return official
