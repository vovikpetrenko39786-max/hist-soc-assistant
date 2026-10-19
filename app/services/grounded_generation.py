from __future__ import annotations
import json

import uuid

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import GenerationRun
from app.schemas.generation import LessonArtifact, LessonGenerationRequest
from app.schemas.retrieval import RetrievalRequest
from app.services.catalog import CurriculumCatalogService
from app.services.curriculum_resolver import CurriculumResolver
from app.services.generation_context import GroundedContextBuilder
from app.services.llm_provider import GenerationProviderError, get_generation_provider
from app.services.quality_gate import LessonQualityGate
from app.services.retrieval import RetrievalService

settings = get_settings()


def _json_safe(value):
    return json.loads(
        json.dumps(value, ensure_ascii=False, default=str)
    )


def _ground_source_references(
    artifact: LessonArtifact,
    source_manifest: list[dict],
) -> None:
    """Replace LLM-produced source metadata with canonical manifest metadata.

    The model may choose a chunk_id, but metadata for a known chunk is owned
    by the retrieval manifest. Unknown chunk_ids are deliberately left
    untouched so the quality gate can reject them.
    """
    manifest_by_chunk = {
        str(item["chunk_id"]): item
        for item in source_manifest
        if item.get("chunk_id")
    }

    for ref in artifact.source_references:
        manifest = manifest_by_chunk.get(str(ref.chunk_id))
        if manifest is None:
            continue

        if manifest.get("source_id") is not None:
            ref.source_id = str(manifest["source_id"])

        ref.source_key = manifest.get("source_key")
        ref.title = (
            manifest.get("title")
            or manifest.get("source_title")
            or ref.title
        )
        ref.url = manifest.get("url")
        ref.section = manifest.get("section")
        ref.page_pdf_start = manifest.get("page_pdf_start")
        ref.page_pdf_end = manifest.get("page_pdf_end")
        ref.page_print_start = manifest.get("page_print_start")
        ref.page_print_end = manifest.get("page_print_end")
        ref.quote_safe = bool(manifest.get("quote_safe", False))


class GroundedGenerationError(RuntimeError):
    pass


class GroundedLessonService:
    def __init__(self):
        self.resolver = CurriculumResolver()
        self.catalog = CurriculumCatalogService()
        self.retrieval = RetrievalService()
        self.context_builder = GroundedContextBuilder()
        self.quality_gate = LessonQualityGate()

    async def generate(
        self,
        session: AsyncSession,
        request: LessonGenerationRequest,
    ) -> dict:
        topic = await self.resolver.resolve_topic(
            session,
            topic_id=request.topic_id,
            topic_text=request.topic,
            subject=request.subject,
            grade=request.grade,
            level=request.level,
        )

        topic_card = await self.catalog.get_topic_card(session, topic.id)
        if topic_card is None:
            raise GroundedGenerationError("Resolved topic has no Topic Card")

        retrieval_request = RetrievalRequest(
            query=request.topic or topic.title,
            mode=request.retrieval_mode,
            subject=topic_card["subject"]["code"],
            grade=topic_card["grade"],
            level=topic_card["curriculum"]["level"],
            topic_id=topic.id,
            source_key=request.source_key,
            strict_source=request.strict_source,
            top_k=request.retrieval_top_k,
            candidate_k=max(20, request.retrieval_top_k * 5),
        )
        retrieval = await self.retrieval.retrieve(session, retrieval_request)

        context = self.context_builder.build_lesson_context(
            request=request,
            topic_card=topic_card,
            retrieval=retrieval,
        )
        prompt_hash = self.context_builder.prompt_hash(context)

        if request.dry_run:
            run_id = None
            if request.save_run:
                run = GenerationRun(
                    task_type="lesson",
                    topic_id=topic.id,
                    provider="none",
                    model="none",
                    prompt_hash=prompt_hash,
                    request_json=_json_safe(request.model_dump(mode="json")),
                    context_json=_json_safe(context),
                    source_manifest=_json_safe(context["source_manifest"]),
                    output_json={},
                    quality_report={},
                    status="dry_run",
                    dry_run=True,
                )
                session.add(run)
                await session.commit()
                await session.refresh(run)
                run_id = run.id

            return {
                "status": "dry_run",
                "topic_card": topic_card,
                "retrieval": retrieval,
                "generation_context": context,
                "artifact": None,
                "quality": None,
                "run_id": run_id,
            }

        provider = get_generation_provider()
        try:
            raw = await provider.generate_lesson(context)
            artifact = LessonArtifact.model_validate(raw)
            _ground_source_references(
                artifact,
                context["source_manifest"],
            )
        except (GenerationProviderError, ValidationError) as exc:
            raise GroundedGenerationError(str(exc)) from exc

        quality = self.quality_gate.evaluate(
            artifact,
            topic_card,
            context["source_manifest"],
        )

        run_id = None
        if request.save_run:
            run = GenerationRun(
                task_type="lesson",
                topic_id=topic.id,
                provider=provider.name,
                model=provider.model,
                prompt_hash=prompt_hash,
                request_json=_json_safe(request.model_dump(mode="json")),
                context_json=_json_safe(context),
                source_manifest=_json_safe(context["source_manifest"]),
                output_json=_json_safe(artifact.model_dump(mode="json")),
                quality_report=_json_safe(quality),
                status="generated" if quality["passed"] else "quality_failed",
                dry_run=False,
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            run_id = run.id

        return {
            "status": "generated" if quality["passed"] else "quality_failed",
            "topic_card": topic_card,
            "retrieval": retrieval,
            "generation_context": context,
            "artifact": artifact.model_dump(mode="json"),
            "quality": quality,
            "run_id": run_id,
        }
