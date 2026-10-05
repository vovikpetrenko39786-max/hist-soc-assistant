"""Dependency-free validation for the universal curriculum JSON dataset."""
from __future__ import annotations

import json
from pathlib import Path

DATASET = Path(__file__).resolve().parents[1] / "data" / "official_curriculum_seed_2026_2027.json"


def validate(path: Path = DATASET) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    source_keys = {x["key"] for x in data["sources"]}
    curriculum_keys = set()
    errors: list[str] = []
    warnings: list[str] = []
    stats = {
        "sources": len(data["sources"]),
        "curricula": 0,
        "units": 0,
        "topics": 0,
        "topics_with_concepts": 0,
        "topic_outcomes": 0,
        "topic_skill_links": 0,
        "exam_links": 0,
        "interdisciplinary_links": 0,
    }

    for c in data["curricula"]:
        stats["curricula"] += 1
        if c["key"] in curriculum_keys:
            errors.append(f"duplicate curriculum key: {c['key']}")
        curriculum_keys.add(c["key"])
        if c["official_source"] not in source_keys:
            errors.append(f"missing source {c['official_source']} for {c['key']}")
        if not 1 <= c["grade"] <= 11:
            errors.append(f"invalid grade for {c['key']}")
        if "skeleton" in str(c.get("coverage", "")):
            errors.append(f"skeleton coverage remains: {c['key']}")

        calculated_hours = 0
        all_units_have_hours = True
        for u_i, unit in enumerate(c.get("units", []), start=1):
            stats["units"] += 1
            if unit.get("hours") is None:
                all_units_have_hours = False
            else:
                calculated_hours += unit["hours"]

            topic_hours = 0
            all_topics_have_hours = bool(unit.get("topics"))
            for t_i, topic in enumerate(unit.get("topics", []), start=1):
                stats["topics"] += 1
                if not topic.get("title"):
                    errors.append(f"empty topic title: {c['key']} unit {u_i} topic {t_i}")
                if topic.get("hours") is None:
                    all_topics_have_hours = False
                else:
                    topic_hours += topic["hours"]
                if topic.get("concepts"):
                    stats["topics_with_concepts"] += 1
                stats["topic_outcomes"] += len(topic.get("outcomes", []))
                stats["topic_skill_links"] += len(topic.get("skills", []))
                stats["exam_links"] += len(topic.get("exam_links", []))
                stats["interdisciplinary_links"] += len(topic.get("interdisciplinary_links", []))

                for field in [
                    "default_lesson_blueprint",
                    "typical_misconceptions",
                    "essential_questions",
                    "reflection_patterns",
                    "assessment_skills",
                    "outcomes",
                    "skills",
                ]:
                    if not topic.get(field):
                        errors.append(f"missing {field}: {c['key']} / {topic.get('title')}")

                for exam in topic.get("exam_links", []):
                    skey = exam.get("source_key")
                    if skey and skey not in source_keys:
                        errors.append(f"missing exam source {skey}: {c['key']} / {topic['title']}")
                    if exam.get("exam_year") == 2027 and exam.get("mapping_level") != "general_topic":
                        warnings.append(f"check 2027 mapping level: {c['key']} / {topic['title']}")

            if all_topics_have_hours and unit.get("hours") is not None and topic_hours != unit["hours"]:
                errors.append(
                    f"topic hours mismatch {c['key']} / {unit['title']}: topics={topic_hours}, unit={unit['hours']}"
                )

        if all_units_have_hours and c.get("total_hours") is not None and calculated_hours != c["total_hours"]:
            errors.append(f"hours mismatch {c['key']}: units={calculated_hours}, total={c['total_hours']}")

    return {"ok": not errors, "errors": errors, "warnings": warnings, "stats": stats}


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)
