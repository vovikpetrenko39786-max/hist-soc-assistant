import asyncio
import json
import sys
import types
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import pgvector.sqlalchemy  # noqa: F401
except ModuleNotFoundError:
    from sqlalchemy import JSON
    pkg = types.ModuleType("pgvector")
    sub = types.ModuleType("pgvector.sqlalchemy")
    class Vector(JSON):
        pass
    sub.Vector = Vector
    pkg.sqlalchemy = sub
    sys.modules["pgvector"] = pkg
    sys.modules["pgvector.sqlalchemy"] = sub

from app.schemas.generation import LessonArtifact, LessonGenerationRequest
from app.services.generation_context import GroundedContextBuilder
from app.services.llm_provider import TemplateLessonProvider
from app.services.quality_gate import LessonQualityGate


async def main():
    req = LessonGenerationRequest(
        subject="HISTORY",
        grade=6,
        level="basic",
        topic="Древняя Русь",
        duration_minutes=45,
    )
    card = {
        "subject": {"code": "HISTORY", "name": "История"},
        "grade": 6,
        "curriculum": {"level": "basic", "title": "История 6"},
        "unit": {"title": "Древняя Русь"},
        "topic": {
            "title": "Древняя Русь",
            "essential_questions": ["Как складывалось Древнерусское государство?"],
        },
        "outcomes": [
            {
                "type": "subject",
                "text": "Объяснять причины и условия формирования государства.",
                "priority": 1,
            }
        ],
        "concepts": [
            {"term": "государство", "importance": "required"},
            {"term": "князь", "importance": "required"},
        ],
        "skills": [],
        "interdisciplinary_links": [],
        "exam_links": [],
    }
    retrieval = {
        "hits": [
            {
                "chunk_id": uuid.uuid4(),
                "source_id": uuid.uuid4(),
                "source_key": "TEST",
                "source_title": "Test textbook",
                "source_status": "primary",
                "section": "§1",
                "page_pdf_start": 10,
                "page_pdf_end": 10,
                "page_print_start": 8,
                "page_print_end": 8,
                "quote_safe": False,
                "snippet": "Test evidence.",
            }
        ]
    }

    builder = GroundedContextBuilder()
    context = builder.build_lesson_context(req, card, retrieval)
    artifact = LessonArtifact.model_validate(
        await TemplateLessonProvider().generate_lesson(context)
    )
    report = LessonQualityGate().evaluate(
        artifact, card, context["source_manifest"]
    )
    print(json.dumps({
        "timeline_minutes": sum(x.minutes for x in artifact.timeline),
        "source_refs": len(artifact.source_references),
        "quality_passed": report["passed"],
        "quality_score": report["score"],
        "prompt_hash_length": len(builder.prompt_hash(context)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
