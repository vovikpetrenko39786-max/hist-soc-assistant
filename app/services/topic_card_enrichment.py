from __future__ import annotations

from collections.abc import Mapping
from typing import Any

ENRICHMENT_VERSION = "topic_card_enrichment_v0_1"
PILOT_TOPIC_TITLE = "Как устроено общество"

PILOT_ENRICHMENT = {
    "content_summary": (
        "Общество можно рассматривать как целостную систему взаимосвязанных элементов, "
        "а не только как совокупность отдельных людей. Общественные отношения связывают "
        "людей и группы и помогают объяснить, как элементы общества взаимодействуют. "
        "Чтобы описать устройство конкретного общества, нужно назвать его элементы, "
        "показать связи между ними и рассмотреть, как изменение одной связи может "
        "повлиять на другие. В этой теме ученик применяет понятия «общество», "
        "«общественные отношения» и «общественная система» к анализу социальных "
        "ситуаций и примеров."
    ),
    "common_examples": [
        {
            "title": "Семья",
            "description": (
                "Родственные связи и распределение повседневных обязанностей показывают, "
                "как людей объединяют устойчивые отношения и взаимодействие."
            ),
        },
        {
            "title": "Школа",
            "description": (
                "Взаимодействие учеников, учителей и администрации позволяет рассмотреть "
                "разные элементы организации и связи между ними."
            ),
        },
        {
            "title": "Местное сообщество",
            "description": (
                "Жители, объединения и местные учреждения взаимодействуют вокруг общих "
                "вопросов; пример помогает проследить связи между группами и организациями."
            ),
        },
    ],
    "counterexamples": [
        {
            "title": "Люди, случайно ожидающие автобус",
            "description": (
                "Совместное нахождение в одном месте само по себе не показывает "
                "устойчивых общественных отношений или устройство общества."
            ),
        },
        {
            "title": "Перечень учреждений без описания связей",
            "description": (
                "Назвать несколько организаций недостаточно, чтобы объяснить структуру: "
                "нужно показать, как они и связанные с ними группы взаимодействуют."
            ),
        },
    ],
    "typical_misconceptions": [
        "Общество сводится к простой совокупности людей, поэтому связи между людьми и группами не учитываются.",
        "Общественные отношения понимаются только как личное общение, а не как связи и взаимодействия между элементами общества.",
        "Структуру общества считают простым перечнем групп или учреждений, не объясняя отношений между ними.",
    ],
    "essential_questions": [
        "Почему общество рассматривают как систему, а не только как совокупность отдельных людей?",
        "Какие общественные отношения связывают людей и группы в рассмотренном примере?",
        "Как изменение связи между элементами общества может повлиять на другие его элементы?",
    ],
    "suitable_activities": [
        {
            "activity": "case_analysis",
            "purpose": "Выделить элементы общества в социальной ситуации.",
            "student_action": "Назвать людей или группы в примере и описать их взаимодействие.",
        },
        {
            "activity": "concept_sort",
            "purpose": "Различить элементы общества и отношения между ними.",
            "student_action": "Разнести карточки с элементами и связями по двум группам и обосновать выбор.",
        },
        {
            "activity": "example_counterexample",
            "purpose": "Проверить, достаточно ли примера для вывода о наличии общественных отношений.",
            "student_action": "Сопоставить школу как организованную систему взаимодействий со случайной очередью людей.",
        },
        {
            "activity": "mini_debate",
            "purpose": "Обосновать системное понимание общества.",
            "student_action": "Аргументировать, почему одного перечня групп недостаточно для описания устройства общества.",
        },
    ],
}

_PENDING_STATUSES = {
    "pending_enrichment",
    "pending_verification",
    "pending_field_verification",
    "pending_review",
}


def topic_card_provenance(topic_item: dict, source_key: str) -> dict:
    fields = {
        "subject": "official_direct",
        "grade": "official_direct",
        "level": "official_direct",
        "curriculum": "official_direct",
        "unit": "official_direct",
        "topic": "official_direct",
        "hours": "official_direct",
        "aliases": "official_direct",
        "learning_outcomes": "generated_candidate",
        "key_concepts": "methodical_mapping",
        "skills": "methodical_mapping",
        "interdisciplinary_links": "methodical_mapping",
        "exam_links": "methodical_mapping",
        "typical_misconceptions": "generated_candidate",
        "common_examples": "generated_candidate",
        "counterexamples": "generated_candidate",
        "essential_questions": "generated_candidate",
        "suitable_activities": "methodical_mapping",
        "default_lesson_blueprint": "methodical_mapping",
        "reflection_patterns": "methodical_mapping",
        "assessment_skills": "methodical_mapping",
        "difficulty_level": "methodical_mapping",
        "abstraction_level": "methodical_mapping",
        "source_references": "official_direct",
    }
    present = {
        "aliases": topic_item.get("aliases"),
        "learning_outcomes": topic_item.get("outcomes"),
        "key_concepts": topic_item.get("concepts"),
        "skills": topic_item.get("skills"),
        "interdisciplinary_links": topic_item.get("interdisciplinary_links"),
        "exam_links": topic_item.get("exam_links"),
        "typical_misconceptions": topic_item.get("typical_misconceptions"),
        "common_examples": topic_item.get("common_examples"),
        "counterexamples": topic_item.get("counterexamples"),
        "essential_questions": topic_item.get("essential_questions"),
        "suitable_activities": topic_item.get("suitable_activities")
        or (topic_item.get("default_lesson_blueprint") or {}).get("recommended_activities"),
        "default_lesson_blueprint": topic_item.get("default_lesson_blueprint"),
        "reflection_patterns": topic_item.get("reflection_patterns"),
        "assessment_skills": topic_item.get("assessment_skills"),
        "difficulty_level": topic_item.get("difficulty_level"),
        "abstraction_level": topic_item.get("abstraction_level"),
        "source_references": topic_item.get("source_references"),
        "content_summary": topic_item.get("content_summary"),
    }
    result = {
        name: {
            "origin": origin,
            "source_key": source_key,
            "status": "pending_verification",
        }
        for name, origin in fields.items()
    }
    for name, value in present.items():
        if not value:
            result[name] = {"status": "pending_enrichment"}
    if not present["content_summary"]:
        result["content_summary"] = {"status": "pending_enrichment"}
    return {**result, **(topic_item.get("provenance") or {})}


def _is_enrich_placeholder(value: Any) -> bool:
    return isinstance(value, str) and value.strip().upper() == "ENRICH"


def _is_empty(value: Any) -> bool:
    if _is_enrich_placeholder(value):
        return True
    if isinstance(value, list):
        return value == [] or all(_is_enrich_placeholder(item) for item in value)
    return value is None or value == "" or value == {}


def sanitize_topic_card_output(card: Mapping[str, Any]) -> dict[str, Any]:
    def clean(value: Any) -> Any:
        if _is_enrich_placeholder(value):
            return None
        if isinstance(value, list):
            cleaned = []
            for item in value:
                normalized = clean(item)
                if normalized is not None:
                    cleaned.append(normalized)
            return cleaned
        if isinstance(value, Mapping):
            return {key: clean(item) for key, item in value.items()}
        return value

    return clean(dict(card))


def _may_replace(topic: Any, field: str, current_value: Any) -> bool:
    if _is_empty(current_value):
        return True
    field_provenance = (topic.provenance or {}).get(field, {})
    return field_provenance.get("status") in _PENDING_STATUSES


def build_topic_card_enrichment(topic: Any, card: Mapping[str, Any]) -> dict[str, Any]:
    """Build the addressable pilot update from the pilot's existing catalog evidence."""
    patch: dict[str, Any] = {}
    card_topic = card.get("topic", {})
    subject = card.get("subject", {})
    if (
        subject.get("code") != "SOCIAL_STUDIES"
        or card.get("grade") != 9
        or card.get("level") != "basic"
        or card_topic.get("title") != PILOT_TOPIC_TITLE
    ):
        return patch

    official_source_keys = sorted({
        item.get("source_key") or item.get("url")
        for item in card.get("source_references", [])
        if (item.get("source_key") or item.get("url")) and item.get("source_role") == "official_program"
    })
    concepts = card.get("key_concepts", [])
    outcomes = card.get("learning_outcomes", [])
    if not official_source_keys or not concepts or not outcomes:
        return patch

    exam_source_keys = sorted({
        item.get("source_key") or item.get("url")
        for item in card.get("source_references", [])
        if (item.get("source_key") or item.get("url")) and item.get("source_role") == "exam"
    })
    source_key = official_source_keys[0] if official_source_keys else ""
    blueprint = card_topic.get("default_lesson_blueprint", {})
    seed_shape = {
        "aliases": card.get("aliases"),
        "outcomes": card.get("learning_outcomes"),
        "concepts": card.get("key_concepts"),
        "skills": card.get("skills"),
        "interdisciplinary_links": card.get("interdisciplinary_links"),
        "exam_links": card.get("exam_links"),
        "typical_misconceptions": card.get("typical_misconceptions"),
        "common_examples": card.get("common_examples"),
        "counterexamples": card.get("counterexamples"),
        "essential_questions": card.get("essential_questions"),
        "suitable_activities": topic.suitable_activities,
        "default_lesson_blueprint": blueprint,
        "reflection_patterns": card_topic.get("reflection_patterns"),
        "assessment_skills": card_topic.get("assessment_skills"),
        "difficulty_level": card_topic.get("difficulty_level"),
        "abstraction_level": card_topic.get("abstraction_level"),
        "source_references": card.get("source_references"),
        "content_summary": topic.content_summary,
    }
    provenance = {
        **topic_card_provenance(seed_shape, source_key),
        **(topic.provenance or {}),
    }
    if exam_source_keys and provenance.get("exam_links", {}).get("status") != "pending_enrichment":
        provenance["exam_links"] = {
            **provenance["exam_links"],
            "source_key": exam_source_keys[0],
        }
    if "interdisciplinary_links" in provenance:
        provenance["interdisciplinary_links"] = {
            key: value
            for key, value in provenance["interdisciplinary_links"].items()
            if key != "source_key"
        }

    generated_fields = {
        "content_summary": {
            "value": PILOT_ENRICHMENT["content_summary"],
            "origin": "generated_candidate",
            "based_on": ["key_concepts", "learning_outcomes"],
        },
        "common_examples": {
            "value": PILOT_ENRICHMENT["common_examples"],
            "origin": "methodical_mapping",
            "based_on": ["key_concepts", "learning_outcomes", "skills"],
        },
        "counterexamples": {
            "value": PILOT_ENRICHMENT["counterexamples"],
            "origin": "methodical_mapping",
            "based_on": ["key_concepts", "learning_outcomes"],
        },
        "typical_misconceptions": {
            "value": PILOT_ENRICHMENT["typical_misconceptions"],
            "origin": "generated_candidate",
            "based_on": ["key_concepts", "learning_outcomes"],
        },
        "essential_questions": {
            "value": PILOT_ENRICHMENT["essential_questions"],
            "origin": "generated_candidate",
            "based_on": ["key_concepts", "learning_outcomes"],
        },
        "suitable_activities": {
            "value": PILOT_ENRICHMENT["suitable_activities"],
            "origin": "methodical_mapping",
            "based_on": ["key_concepts", "learning_outcomes", "skills"],
        },
    }
    for field, spec in generated_fields.items():
        current_value = getattr(topic, field, None)
        if not _may_replace(topic, field, current_value):
            continue
        if current_value == spec["value"]:
            continue
        patch[field] = spec["value"]
        provenance[field] = {
            "origin": spec["origin"],
            "status": "pending_review",
            "pipeline": ENRICHMENT_VERSION,
            "based_on": spec["based_on"],
            "source_keys": official_source_keys,
        }

    for field in ("default_lesson_blueprint", "reflection_patterns"):
        current_provenance = provenance.get(field, {})
        if current_provenance.get("role") == "system_fallback":
            continue
        if current_provenance.get("status") not in _PENDING_STATUSES:
            continue
        provenance[field] = {
            **current_provenance,
            "origin": "methodical_mapping",
            "status": current_provenance.get("status", "pending_review"),
            "role": "system_fallback",
            "specific_to_topic": False,
        }

    if provenance != (topic.provenance or {}):
        patch["provenance"] = provenance

    if patch:
        content_fields = set(generated_fields)
        if content_fields.intersection(patch) and topic.derivation_status in (
            None,
            "",
            "pending_enrichment",
        ):
            patch["derivation_status"] = "mixed_official_and_methodical"
        if content_fields.intersection(patch):
            patch["verification_status"] = "pending_review"

    return patch


def apply_topic_card_enrichment(topic: Any, patch: Mapping[str, Any]) -> None:
    for field, value in patch.items():
        setattr(topic, field, value)
