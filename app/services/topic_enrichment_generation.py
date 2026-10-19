from __future__ import annotations

import re
from functools import lru_cache

from collections.abc import Mapping
from typing import Any, Protocol

import pymorphy3

from app.schemas.generation import TopicEnrichmentArtifact
from app.services.generation_context import GroundedContextBuilder


class TopicEnrichmentGenerationError(RuntimeError):
    pass


class TopicEnrichmentProvider(Protocol):
    async def generate_topic_enrichment(self, context: dict) -> dict:
        ...


_MATERIAL_DEPENDENCY_PATTERN = re.compile(
    r"\b(?:"
    r"карт(?:а|ы|у|е|ой|ами|ах)?|"
    r"источник\w*|"
    r"документ\w*|"
    r"статистик\w*|"
    r"диаграм\w*|"
    r"иллюстрац\w*|"
    r"фотограф\w*|"
    r"цитат\w*|"
    r"отрывок\w*"
    r")\b",
    re.IGNORECASE,
)


def _normalize_label(value: str | None) -> str:
    return " ".join(
        re.sub(
            r"[^\w]+",
            " ",
            value or "",
            flags=re.UNICODE,
        ).casefold().split()
    )


_TOKEN_RE = re.compile(
    r"[A-Za-zА-Яа-яЁё0-9]+",
    re.UNICODE,
)

_CYRILLIC_WORD_RE = re.compile(
    r"[А-Яа-яЁё]{5,}",
    re.UNICODE,
)

_SHORT_LEFT_WORDS = {
    "и",
    "а",
    "но",
    "что",
    "как",
    "не",
    "в",
    "к",
    "с",
    "о",
    "у",
    "на",
    "по",
    "из",
}


@lru_cache(maxsize=1)
def _morph_analyzer() -> pymorphy3.MorphAnalyzer:
    return pymorphy3.MorphAnalyzer()


def _joined_word_split(
    word: str,
) -> tuple[str, str] | None:
    low = word.casefold()
    morph = _morph_analyzer()

    if morph.word_is_known(low):
        return None

    for index in range(1, len(low)):
        left = low[:index]
        right = low[index:]

        if not morph.word_is_known(left):
            continue
        if not morph.word_is_known(right):
            continue

        normal_lengths = (
            len(left) >= 3
            and len(right) >= 3
        )
        short_function_word = (
            left in _SHORT_LEFT_WORDS
            and len(right) >= 4
        )

        if normal_lengths or short_function_word:
            return left, right

    return None


def _artifact_texts(
    artifact: TopicEnrichmentArtifact,
):
    payload = artifact.model_dump(mode="python")

    def walk(value):
        if isinstance(value, str):
            yield value
            return

        if isinstance(value, Mapping):
            for item in value.values():
                yield from walk(item)
            return

        if isinstance(value, list):
            for item in value:
                yield from walk(item)

    yield from walk(payload)


def _validate_text_quality(
    artifact: TopicEnrichmentArtifact,
) -> None:
    for text in _artifact_texts(artifact):
        for word in _CYRILLIC_WORD_RE.findall(text):
            split = _joined_word_split(word)
            if split is None:
                continue

            left, right = split
            raise TopicEnrichmentGenerationError(
                "Generated enrichment contains a suspicious "
                f"joined word: {word} -> {left} + {right}"
            )


def _token_key(token: str) -> str:
    token = token.casefold()
    if len(token) >= 7:
        return token[:5]
    if len(token) >= 5:
        return token[:4]
    return token


def _concept_keys(value: str | None) -> set[str]:
    tokens = _TOKEN_RE.findall(value or "")
    substantial = [
        token
        for token in tokens
        if len(token) >= 4
    ]
    selected = substantial or [
        token
        for token in tokens
        if len(token) >= 2
    ]
    return {
        _token_key(token)
        for token in selected
    }


def _evidence_concept_coverage(
    snippet: str,
    concept_terms: list[str],
) -> int:
    snippet_keys = {
        _token_key(token)
        for token in _TOKEN_RE.findall(snippet)
    }

    coverage = 0
    for term in concept_terms:
        keys = _concept_keys(term)
        if not keys:
            continue

        overlap = len(keys & snippet_keys)
        required = 1 if len(keys) == 1 else 2

        if overlap >= required:
            coverage += 1

    return coverage


def _select_relevant_source_manifest(
    card: Mapping[str, Any],
    source_manifest: list[dict],
) -> list[dict]:
    concepts = (
        card.get("key_concepts")
        or card.get("concepts")
        or []
    )
    concept_terms = [
        str(item.get("term"))
        for item in concepts
        if item.get("term")
    ]

    scored = [
        (
            _evidence_concept_coverage(
                item.get("snippet") or "",
                concept_terms,
            ),
            index,
            item,
        )
        for index, item in enumerate(source_manifest)
        if item.get("snippet")
    ]

    if not scored:
        return []

    max_coverage = max(
        coverage
        for coverage, _, _ in scored
    )

    threshold = 2 if max_coverage >= 2 else 1

    return [
        item
        for coverage, _, item in scored
        if coverage >= threshold
    ][:6]


def _validate_generated_artifact(
    artifact: TopicEnrichmentArtifact,
    context: Mapping[str, Any],
) -> None:
    concept_labels = {
        _normalize_label(item.get("term"))
        for item in (context.get("key_concepts") or [])
        if item.get("term")
    }
    example_labels = [
        _normalize_label(item.title)
        for item in artifact.common_examples
        if item.title
    ]

    if (
        example_labels
        and concept_labels
        and all(label in concept_labels for label in example_labels)
    ):
        raise TopicEnrichmentGenerationError(
            "Generated common examples only restate key concepts."
        )

    _validate_text_quality(artifact)

    if not context.get("available_materials"):
        for activity in artifact.suitable_activities:
            activity_text = " ".join(
                [
                    activity.activity,
                    activity.purpose,
                    activity.student_action,
                ]
            )
            match = _MATERIAL_DEPENDENCY_PATTERN.search(
                activity_text
            )
            if match:
                raise TopicEnrichmentGenerationError(
                    "Generated activity depends on unavailable "
                    f"learning material: {match.group(0)}"
                )


def build_topic_enrichment_context(
    card: Mapping[str, Any],
    retrieval: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    subject = card.get("subject") or {}
    topic = card.get("topic") or {}

    concepts = (
        card.get("key_concepts")
        or card.get("concepts")
        or []
    )
    outcomes = (
        card.get("learning_outcomes")
        or card.get("outcomes")
        or []
    )
    skills = card.get("skills") or []
    available_materials = [
        item
        for item in (card.get("available_materials") or [])
        if isinstance(item, Mapping)
    ]

    source_manifest = GroundedContextBuilder.source_manifest(
        dict(retrieval or {})
    )
    relevant_manifest = _select_relevant_source_manifest(
        card,
        source_manifest,
    )
    retrieved_evidence = [
        {
            "chunk_id": item.get("chunk_id"),
            "source_title": (
                item.get("source_title")
                or item.get("title")
            ),
            "status": item.get("status"),
            "section": item.get("section"),
            "page_pdf_start": item.get("page_pdf_start"),
            "page_pdf_end": item.get("page_pdf_end"),
            "page_print_start": item.get("page_print_start"),
            "page_print_end": item.get("page_print_end"),
            "snippet": item.get("snippet"),
        }
        for item in relevant_manifest
    ]

    official_sources = [
        source
        for source in (card.get("source_references") or [])
        if source.get("source_role") == "official_program"
    ]

    if not subject.get("code"):
        raise TopicEnrichmentGenerationError(
            "Topic Card has no subject code."
        )

    if not topic.get("title"):
        raise TopicEnrichmentGenerationError(
            "Topic Card has no topic title."
        )

    if not concepts:
        raise TopicEnrichmentGenerationError(
            "Topic Card has no key concepts."
        )

    if not outcomes:
        raise TopicEnrichmentGenerationError(
            "Topic Card has no learning outcomes."
        )

    if not official_sources:
        raise TopicEnrichmentGenerationError(
            "Topic Card has no official program source."
        )

    if not retrieved_evidence:
        raise TopicEnrichmentGenerationError(
            "Topic enrichment requires retrieved evidence."
        )

    return {
        "subject": {
            "code": subject.get("code"),
            "name": subject.get("name"),
        },
        "grade": card.get("grade"),
        "level": card.get("level"),
        "topic": {
            "title": topic.get("title"),
            "description": topic.get("description"),
        },
        "key_concepts": [
            {
                "term": item.get("term"),
                "importance": item.get("importance"),
            }
            for item in concepts
        ],
        "learning_outcomes": [
            {
                "type": item.get("type"),
                "subtype": item.get("subtype"),
                "text": item.get("text"),
                "priority": item.get("priority"),
            }
            for item in outcomes
        ],
        "skills": [
            {
                "code": item.get("code"),
                "name": item.get("name"),
                "category": item.get("category"),
                "priority": item.get("priority"),
            }
            for item in skills
        ],
        "available_materials": [
            {
                "type": item.get("type"),
                "title": item.get("title"),
                "description": item.get("description"),
            }
            for item in available_materials
        ],
        "retrieved_evidence": retrieved_evidence,
        "official_sources": [
            {
                "title": item.get("title"),
                "section": item.get("section"),
                "source_role": item.get("source_role"),
            }
            for item in official_sources
        ],
    }


class TopicEnrichmentGenerationService:
    def __init__(self, provider: TopicEnrichmentProvider):
        self.provider = provider

    async def generate(
        self,
        card: Mapping[str, Any],
        retrieval: Mapping[str, Any],
    ) -> TopicEnrichmentArtifact:
        context = build_topic_enrichment_context(
            card,
            retrieval,
        )

        raw = await self.provider.generate_topic_enrichment(context)

        artifact = TopicEnrichmentArtifact.model_validate(raw)
        _validate_generated_artifact(artifact, context)

        return artifact
