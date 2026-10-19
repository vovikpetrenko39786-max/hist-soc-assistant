"""Safely persist Topic Card enrichment for a selected catalog topic."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from uuid import UUID

from app.db.session import SessionLocal
from app.models.catalog import Topic
from app.services.catalog import CurriculumCatalogService
from app.services.topic_card_enrichment import (
    apply_topic_card_enrichment,
    build_topic_card_enrichment,
)


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
        **{
            key: value
            for key, value in patch.items()
            if key in topic_patch_fields
        },
    }
    return updated


async def enrich_topic(*, topic_id: UUID, apply: bool) -> int:
    async with SessionLocal() as session:
        topic = await session.get(Topic, topic_id)
        if topic is None:
            print(
                f"Topic {topic_id} not found in the current catalog.",
                file=sys.stderr,
            )
            return 1

        card = await CurriculumCatalogService().get_topic_card(
            session,
            topic.id,
        )
        if card is None:
            print(
                "Topic Card has no complete curriculum context.",
                file=sys.stderr,
            )
            return 1

        patch = build_topic_card_enrichment(topic, card)
        if not patch:
            print(
                "No enrichment changes can be built for this Topic Card.",
                file=sys.stderr,
            )
            return 1

        apply_topic_card_enrichment(topic, patch)

        if apply:
            await session.commit()
        else:
            await session.rollback()

        print(
            json.dumps(
                _updated_card(card, patch),
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        print(
            "Changes committed."
            if apply
            else "Dry run only; no changes committed."
        )

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build Topic Card enrichment for a selected topic. "
            "The default mode is read-only; use --apply to persist changes."
        )
    )
    parser.add_argument(
        "--topic-id",
        type=UUID,
        required=True,
        help="Catalog Topic UUID to enrich.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Persist changes to the configured database; "
            "without this flag the transaction is rolled back."
        ),
    )

    args = parser.parse_args()

    raise SystemExit(
        asyncio.run(
            enrich_topic(
                topic_id=args.topic_id,
                apply=args.apply,
            )
        )
    )


if __name__ == "__main__":
    main()
