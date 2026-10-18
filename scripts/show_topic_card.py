"""Print one Topic Card already present in the catalog database."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.db.session import SessionLocal
from app.services.catalog import CurriculumCatalogService


async def show_topic_card(subject: str, grade: int, query: str, level: str) -> int:
    service = CurriculumCatalogService()
    async with SessionLocal() as session:
        matches = await service.search_topics(
            session,
            q=query,
            subject_code=subject,
            grade=grade,
            level=level,
            limit=1,
        )
        if not matches:
            print("No matching Topic Card found. Import the official curriculum seed first.", file=sys.stderr)
            return 1
        card = await service.get_topic_card(session, matches[0]["id"])
        print(json.dumps(card, ensure_ascii=False, indent=2, default=str))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Print one existing curriculum Topic Card")
    parser.add_argument("--subject", default="SOCIAL_STUDIES")
    parser.add_argument("--grade", type=int, default=9)
    parser.add_argument("--level", default="basic")
    parser.add_argument("--query", default="Как устроено общество")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(show_topic_card(args.subject, args.grade, args.query, args.level)))


if __name__ == "__main__":
    main()
