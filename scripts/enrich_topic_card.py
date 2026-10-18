"""Safely enrich the single pilot Topic Card from its existing catalog links."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.catalog import (
    Curriculum,
    CurriculumUnit,
    GradeLevel,
    Subject,
    Topic,
)
from app.services.catalog import CurriculumCatalogService
from app.services.topic_card_enrichment import (
    apply_topic_card_enrichment,
    build_topic_card_enrichment,
)

PILOT_SUBJECT = "SOCIAL_STUDIES"
PILOT_GRADE = 9
PILOT_LEVEL = "basic"
PILOT_TITLE = "Как устроено общество"


def _updated_card(card: dict, patch: dict) -> dict:
    updated = {**card, **patch}
    topic_patch_fields = {
        "content_summary",
        "suitable_activities",
        "provenance",
        "derivation_status",
        "verification_status",
    }
    updated["topic"] = {
        **card["topic"],
        **{key: value for key, value in patch.items() if key in topic_patch_fields},
    }
    return updated


async def enrich_pilot_topic(*, apply: bool) -> int:
    stmt = (
        select(Topic)
        .join(CurriculumUnit, Topic.unit_id == CurriculumUnit.id)
        .join(Curriculum, CurriculumUnit.curriculum_id == Curriculum.id)
        .join(Subject, Curriculum.subject_id == Subject.id)
        .join(GradeLevel, Curriculum.grade_level_id == GradeLevel.id)
        .where(
            Subject.code == PILOT_SUBJECT,
            GradeLevel.grade == PILOT_GRADE,
            Curriculum.level == PILOT_LEVEL,
            Curriculum.status == "current",
            Topic.title == PILOT_TITLE,
        )
    )

    async with SessionLocal() as session:
        topic = (await session.execute(stmt)).scalar_one_or_none()
        if topic is None:
            print("Pilot Topic Card not found in the current catalog.", file=sys.stderr)
            return 1

        card = await CurriculumCatalogService().get_topic_card(session, topic.id)
        if card is None:
            print("Pilot Topic Card has no complete curriculum context.", file=sys.stderr)
            return 1

        patch = build_topic_card_enrichment(topic, card)
        if not patch:
            print("No enrichment can be built from the existing linked evidence.", file=sys.stderr)
            return 1

        apply_topic_card_enrichment(topic, patch)
        if apply:
            await session.commit()
        else:
            await session.rollback()

        print(json.dumps(_updated_card(card, patch), ensure_ascii=False, indent=2, default=str))
        print("Changes committed." if apply else "Dry run only; no changes committed.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich only the SOCIAL_STUDIES grade 9 basic pilot Topic Card."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes to the database configured for this process; default is read-only dry run.",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(enrich_pilot_topic(apply=args.apply)))


if __name__ == "__main__":
    main()
