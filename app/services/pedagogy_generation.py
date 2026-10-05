from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import GenerationRun
from app.schemas.pedagogy import PedagogyGenerationRequest
from app.schemas.retrieval import RetrievalRequest
from app.services.catalog import CurriculumCatalogService
from app.services.curriculum_resolver import CurriculumResolver
from app.services.generation_context import GroundedContextBuilder
from app.services.pedagogy_provider import HttpPedagogyProvider, TemplatePedagogyProvider
from app.services.pedagogy_quality import PedagogyQualityGate
from app.services.retrieval import RetrievalService
from app.services.web_knowledge import WebKnowledgeService
from app.services.openai_pedagogy import OpenAIResponsesPedagogyProvider

settings = get_settings()


class PedagogyGenerationError(RuntimeError):
    pass


class PedagogyGenerationService:
    def __init__(self):
        self.resolver = CurriculumResolver()
        self.catalog = CurriculumCatalogService()
        self.retrieval = RetrievalService()
        self.context_builder = GroundedContextBuilder()
        self.quality_gate = PedagogyQualityGate()
        self.web = WebKnowledgeService()

    def _provider(self):
        p = settings.generation_provider.lower().strip()
        if p == "template": return TemplatePedagogyProvider()
        if p == "http": return HttpPedagogyProvider()
        if p == "openai_responses": return OpenAIResponsesPedagogyProvider()
        raise PedagogyGenerationError(f"Unsupported generation provider: {p}")

    async def generate(self, session: AsyncSession, request: PedagogyGenerationRequest) -> dict:
        topic = None; topic_card = None; retrieval = {"hits": [], "warnings": []}
        if request.artifact_type != "idea_enhancement":
            topic = await self.resolver.resolve_topic(
                session, topic_id=request.topic_id, topic_text=request.topic,
                subject=request.subject, grade=request.grade, level=request.level,
            )
            topic_card = await self.catalog.get_topic_card(session, topic.id)
            if not topic_card: raise PedagogyGenerationError("Resolved topic has no Topic Card")
            retrieval = await self.retrieval.retrieve(session, RetrievalRequest(
                query=request.topic or topic.title,
                mode=request.retrieval_mode,
                subject=topic_card["subject"]["code"], grade=topic_card["grade"],
                level=topic_card["curriculum"]["level"], topic_id=topic.id,
                source_key=request.source_key, strict_source=request.strict_source,
                top_k=request.retrieval_top_k, candidate_k=max(20, request.retrieval_top_k * 5),
            ))

        web_query = request.request_text.strip() or (request.topic or (topic.title if topic else ""))
        web_retrieval = await self.web.controlled_fallback(
            session,
            query=web_query,
            policy=request.knowledge_policy,
            subject=(topic_card["subject"]["code"] if topic_card else request.subject),
            topic_id=(topic.id if topic else None),
            local_retrieval=retrieval,
            request_text=request.request_text,
            allow_web_fallback=request.allow_web_fallback,
            strict_source=request.strict_source,
            dry_run=request.dry_run,
            save_run=request.save_run,
        )

        context = self.context_builder.build(
            request, topic_card, retrieval, web_retrieval=web_retrieval
        )
        prompt_hash = self.context_builder.prompt_hash(context)

        if request.dry_run:
            run_id = None
            if request.save_run:
                run = GenerationRun(
                    task_type=request.artifact_type, topic_id=topic.id if topic else None,
                    provider="none", model="none", prompt_hash=prompt_hash,
                    request_json=request.model_dump(mode="json"), context_json=context,
                    source_manifest=context["source_manifest"], output_json={}, quality_report={},
                    status="dry_run", dry_run=True,
                )
                session.add(run); await session.commit(); await session.refresh(run); run_id = run.id
            return {
                "status":"dry_run","artifact_type":request.artifact_type,"topic_card":topic_card,
                "retrieval":retrieval,"web_retrieval":web_retrieval,"generation_context":context,"teacher_artifact":None,
                "student_artifact":None,"quality":None,"run_id":run_id,
            }

        provider = self._provider(); bundle = await provider.generate(context)
        quality = self.quality_gate.evaluate(
            request.artifact_type, bundle["teacher"], bundle.get("student"),
            topic_card, context["source_manifest"],
        )

        run_id = None
        if request.save_run:
            run = GenerationRun(
                task_type=request.artifact_type, topic_id=topic.id if topic else None,
                provider=provider.name, model=provider.model, prompt_hash=prompt_hash,
                request_json=request.model_dump(mode="json"), context_json=context,
                source_manifest=context["source_manifest"], output_json=bundle,
                quality_report=quality, status="generated" if quality["passed"] else "quality_failed",
                dry_run=False,
            )
            session.add(run); await session.commit(); await session.refresh(run); run_id = run.id

        teacher_out = bundle["teacher"] if request.audience in {"teacher","both"} else None
        student_out = bundle.get("student") if request.audience in {"student","both"} else None
        return {
            "status":"generated" if quality["passed"] else "quality_failed",
            "artifact_type":request.artifact_type,"topic_card":topic_card,"retrieval":retrieval,
            "generation_context":context,"teacher_artifact":teacher_out,"student_artifact":student_out,
            "quality":quality,"run_id":run_id,
        }
