"""Trusted Telegram pilot bindings: scoped by Telegram user ID.

Format: {"12345678": {"9b-social": {
  "class_course_id": "UUID", "source_key": "BOOK-KEY", "label": "9-Б обществознание"
}}}

Aliases are only display shortcuts: never accept client-supplied UUIDs as access.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CourseChoice:
    alias: str
    label: str
    class_course_id: UUID
    source_key: str | None


def parse_course_bindings(raw: str | None) -> dict[int, dict[str, CourseChoice]]:
    """Strict parsing; empty string is disabled, malformed config aborts bot boot."""
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("TELEGRAM_COURSE_BINDINGS_JSON is not valid JSON") from exc
    if not isinstance(data, dict) or len(data) > 100:
        raise ValueError("Course bindings must map up to 100 Telegram user IDs")
    result: dict[int, dict[str, CourseChoice]] = {}
    for user_id, courses in data.items():
        if (not isinstance(user_id, str) or not re.fullmatch(r"[1-9][0-9]*", user_id)
                or not isinstance(courses, dict) or len(courses) > 32):
            raise ValueError("Invalid course binding user or course list")
        bound: dict[str, CourseChoice] = {}
        for raw_alias, details in courses.items():
            if (not isinstance(raw_alias, str) or not isinstance(details, dict)
                    or not re.fullmatch(r"[\w\-]{2,40}", raw_alias, re.UNICODE)):
                raise ValueError("Invalid course alias or course definition")
            alias = raw_alias.casefold()
            if alias in bound:
                raise ValueError("Duplicate case-insensitive course alias")
            if set(details) - {"class_course_id", "source_key", "label"}:
                raise ValueError("Unknown course binding field")
            identifier = details.get("class_course_id")
            if not isinstance(identifier, str):
                raise ValueError("Course ID must be a UUID string")  # noqa: TRY004
            try:
                class_course_id = UUID(identifier)
            except (ValueError, AttributeError) as exc:
                raise ValueError("Invalid class_course_id") from exc
            if class_course_id.int == 0 or str(class_course_id) != identifier.lower():
                raise ValueError("Use a nonzero canonical UUID for class_course_id")
            key = details.get("source_key")
            if key is not None and (
                not isinstance(key, str)
                or not 1 <= len(key) <= 150
                or key.strip() != key
                or any(ord(c) < 32 for c in key)
            ):
                raise ValueError("Invalid source_key")
            label = details.get("label", raw_alias)
            if (not isinstance(label, str) or not 1 <= len(label.strip()) <= 100
                    or any(ord(c) < 32 for c in label)):
                raise ValueError("Invalid course label")
            bound[alias] = CourseChoice(alias, label.strip(), class_course_id, key)
        result[int(user_id)] = bound
    return result


def choices_for_user(config: dict[int, dict[str, CourseChoice]], user_id: int | None):
    """No cross-user discovery: never return other users' course IDs."""
    if user_id is None:
        return {}
    return config.get(user_id, {})


def get_selected_choice(config: dict[int, dict[str, CourseChoice]],
                        user_id: int | None, selected_alias: str | None):
    if not isinstance(selected_alias, str):
        return None
    return choices_for_user(config, user_id).get(selected_alias.casefold())


def course_kwargs(choice: CourseChoice | None) -> dict:
    """Only server-typed top-level fields; no arbitrary user_context overrides."""
    if choice is None:
        return {}
    return {
        "class_course_id": str(choice.class_course_id),
        "source_key": choice.source_key,
    }
