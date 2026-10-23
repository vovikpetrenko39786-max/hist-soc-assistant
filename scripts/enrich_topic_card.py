"""Safely persist Topic Card enrichment for a selected catalog topic."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.db.session import SessionLocal
from app.models.catalog import Topic
from app.schemas.generation import TopicEnrichmentArtifact
from app.schemas.retrieval import RetrievalRequest
from app.services.catalog import CurriculumCatalogService
from app.services.llm_provider import get_generation_provider
from app.services.retrieval import RetrievalService
from app.services.topic_card_enrichment import (
    apply_topic_card_enrichment,
    build_generated_topic_card_enrichment,
    build_topic_card_enrichment,
)
from app.services.topic_enrichment_generation import (
    TopicEnrichmentGenerationError,
    TopicEnrichmentGenerationService,
    build_topic_enrichment_context,
)

CANDIDATE_SCHEMA_VERSION = 2
DEFAULT_CANDIDATE_DIR = Path("outputs/topic-enrichment-candidates")
_CANDIDATE_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CANDIDATE_KEYS = {
    "schema_version",
    "candidate_id",
    "topic_id",
    "topic_card_hash",
    "artifact",
    "proposed_patch",
    "evidence_chunk_ids",
}
_GENERATED_CONTENT_FIELDS = {
    "content_summary",
    "common_examples",
    "counterexamples",
    "typical_misconceptions",
    "essential_questions",
    "suitable_activities",
}
_ALLOWED_GENERATED_PATCH_FIELDS = {
    *_GENERATED_CONTENT_FIELDS,
    "provenance",
    "derivation_status",
    "verification_status",
}


class CandidateValidationError(ValueError):
    """Raised when a saved candidate cannot be trusted or applied."""


def _json_value(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )
    )


def _topic_card_hash(card: Mapping[str, Any]) -> str:
    return _candidate_id(_json_value(card))


def _candidate_payload(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": candidate.get("schema_version"),
        "topic_id": candidate.get("topic_id"),
        "topic_card_hash": candidate.get("topic_card_hash"),
        "artifact": candidate.get("artifact"),
        "proposed_patch": candidate.get("proposed_patch"),
        "evidence_chunk_ids": candidate.get("evidence_chunk_ids"),
    }


def _candidate_id(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_candidate(
    *,
    topic_id: UUID,
    topic_card_hash: str,
    artifact: Mapping[str, Any],
    proposed_patch: Mapping[str, Any],
    evidence_chunk_ids: list[str],
) -> dict[str, Any]:
    payload = _json_value(
        {
            "schema_version": CANDIDATE_SCHEMA_VERSION,
            "topic_id": str(topic_id),
            "topic_card_hash": topic_card_hash,
            "artifact": dict(artifact),
            "proposed_patch": dict(proposed_patch),
            "evidence_chunk_ids": list(evidence_chunk_ids),
        }
    )
    return {
        "schema_version": payload["schema_version"],
        "candidate_id": _candidate_id(payload),
        "topic_id": payload["topic_id"],
        "topic_card_hash": payload["topic_card_hash"],
        "artifact": payload["artifact"],
        "proposed_patch": payload["proposed_patch"],
        "evidence_chunk_ids": payload["evidence_chunk_ids"],
    }


def _save_candidate(
    candidate: Mapping[str, Any],
    candidate_dir: Path,
) -> Path:
    candidate_dir.mkdir(parents=True, exist_ok=True)
    path = candidate_dir / f"{candidate['candidate_id']}.json"
    temporary_path = candidate_dir / f".{candidate['candidate_id']}.tmp"
    temporary_path.write_text(
        json.dumps(
            candidate,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, path)
    return path


def _validate_candidate(
    candidate: Any,
    *,
    expected_candidate_id: str,
    expected_topic_id: UUID,
) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise CandidateValidationError("Candidate must be a JSON object.")

    if set(candidate) != _CANDIDATE_KEYS:
        raise CandidateValidationError("Candidate has missing or unsupported fields.")

    if (
        type(candidate["schema_version"]) is not int
        or candidate["schema_version"] != CANDIDATE_SCHEMA_VERSION
    ):
        raise CandidateValidationError("Candidate schema version is not supported.")

    candidate_id = candidate["candidate_id"]
    if not isinstance(candidate_id, str) or not _CANDIDATE_ID_PATTERN.fullmatch(candidate_id):
        raise CandidateValidationError("Candidate ID is malformed.")

    if not hmac.compare_digest(candidate_id, expected_candidate_id):
        raise CandidateValidationError("Candidate ID does not match the requested candidate.")

    try:
        stored_topic_id = UUID(candidate["topic_id"])
    except (TypeError, ValueError, AttributeError) as exc:
        raise CandidateValidationError("Candidate topic ID is malformed.") from exc

    if stored_topic_id != expected_topic_id:
        raise CandidateValidationError("Candidate belongs to a different topic.")

    topic_card_hash = candidate["topic_card_hash"]
    if not isinstance(topic_card_hash, str) or not _CANDIDATE_ID_PATTERN.fullmatch(topic_card_hash):
        raise CandidateValidationError("Candidate Topic Card hash is malformed.")

    artifact = candidate["artifact"]
    if not isinstance(artifact, dict):
        raise CandidateValidationError("Candidate artifact is malformed.")
    try:
        validated_artifact = TopicEnrichmentArtifact.model_validate(artifact)
    except ValidationError as exc:
        raise CandidateValidationError("Candidate artifact is invalid.") from exc
    if validated_artifact.model_dump(mode="json") != artifact:
        raise CandidateValidationError("Candidate artifact contains unsupported fields.")

    evidence_chunk_ids = candidate["evidence_chunk_ids"]
    if (
        not isinstance(evidence_chunk_ids, list)
        or not evidence_chunk_ids
        or any(not isinstance(chunk_id, str) or not chunk_id for chunk_id in evidence_chunk_ids)
    ):
        raise CandidateValidationError("Candidate evidence chunk IDs are invalid.")

    proposed_patch = candidate["proposed_patch"]
    if not isinstance(proposed_patch, dict) or not proposed_patch:
        raise CandidateValidationError("Candidate has no applicable proposed patch.")

    unsupported_fields = set(proposed_patch) - _ALLOWED_GENERATED_PATCH_FIELDS
    if unsupported_fields:
        raise CandidateValidationError(
            "Candidate patch contains unsupported fields: " + ", ".join(sorted(unsupported_fields))
        )

    content_fields = _GENERATED_CONTENT_FIELDS.intersection(proposed_patch)
    if not content_fields:
        raise CandidateValidationError("Candidate patch has no generated content fields.")

    if proposed_patch.get("verification_status") != "pending_review":
        raise CandidateValidationError("Candidate verification status must remain pending_review.")

    if (
        "derivation_status" in proposed_patch
        and proposed_patch["derivation_status"] != "mixed_official_and_methodical"
    ):
        raise CandidateValidationError("Candidate derivation status is invalid.")

    provenance = proposed_patch.get("provenance")
    if not isinstance(provenance, dict):
        raise CandidateValidationError("Candidate patch has no valid provenance.")

    normalized_evidence_ids = sorted(set(evidence_chunk_ids))
    for field in content_fields:
        if proposed_patch[field] != artifact[field]:
            raise CandidateValidationError(
                f"Candidate patch field {field} does not match its artifact."
            )
        field_provenance = provenance.get(field)
        if (
            not isinstance(field_provenance, dict)
            or field_provenance.get("origin") != "generated_candidate"
            or field_provenance.get("status") != "pending_review"
            or field_provenance.get("source_chunk_ids") != normalized_evidence_ids
        ):
            raise CandidateValidationError(f"Candidate patch field {field} has invalid provenance.")

    calculated_id = _candidate_id(_candidate_payload(candidate))
    if not hmac.compare_digest(candidate_id, calculated_id):
        raise CandidateValidationError("Candidate hash does not match its saved contents.")

    return candidate


def _load_candidate(
    *,
    candidate_id: str,
    topic_id: UUID,
    candidate_dir: Path,
) -> dict[str, Any]:
    if not isinstance(candidate_id, str) or not _CANDIDATE_ID_PATTERN.fullmatch(candidate_id):
        raise CandidateValidationError("Candidate ID must be a 64-character SHA-256 hash.")

    path = candidate_dir / f"{candidate_id}.json"
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CandidateValidationError(f"Candidate {candidate_id} could not be read.") from exc

    try:
        candidate = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CandidateValidationError(f"Candidate {candidate_id} is not valid JSON.") from exc

    return _validate_candidate(
        candidate,
        expected_candidate_id=candidate_id,
        expected_topic_id=topic_id,
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
        **{key: value for key, value in patch.items() if key in topic_patch_fields},
    }
    return updated


async def enrich_topic(
    *,
    topic_id: UUID,
    apply: bool,
    generate: bool = False,
    candidate_dir: Path = DEFAULT_CANDIDATE_DIR,
) -> int:
    if generate and apply:
        print(
            "--generate cannot be combined with --apply; generate and "
            "apply the saved candidate in separate commands.",
            file=sys.stderr,
        )
        return 1

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

        if generate:
            provider = get_generation_provider()
            if not hasattr(provider, "generate_topic_enrichment"):
                print(
                    "Configured generation provider does not support Topic Card enrichment.",
                    file=sys.stderr,
                )
                await session.rollback()
                return 1

            curriculum = card.get("curriculum") or {}
            retrieval = await RetrievalService().retrieve(
                session,
                RetrievalRequest(
                    query=card["topic"]["title"],
                    mode="hybrid",
                    subject=card["subject"]["code"],
                    grade=card.get("grade"),
                    level=(curriculum.get("level") or card.get("level")),
                    topic_id=topic.id,
                    top_k=8,
                    candidate_k=40,
                ),
            )

            try:
                artifact = await TopicEnrichmentGenerationService(provider).generate(
                    card,
                    retrieval,
                )

                generation_context = build_topic_enrichment_context(
                    card,
                    retrieval,
                )
            except (TopicEnrichmentGenerationError, ValidationError) as exc:
                await session.rollback()
                print(
                    f"Generated enrichment failed validation: {exc}",
                    file=sys.stderr,
                )
                return 1

            evidence_chunk_ids = [
                str(item["chunk_id"])
                for item in generation_context["retrieved_evidence"]
                if item.get("chunk_id")
            ]

            proposed_patch = build_generated_topic_card_enrichment(
                topic,
                card,
                artifact.model_dump(mode="python"),
                evidence_chunk_ids=evidence_chunk_ids,
            )

            if not proposed_patch or not _GENERATED_CONTENT_FIELDS.intersection(proposed_patch):
                await session.rollback()
                print(
                    "Generated enrichment produced no applicable changes.",
                    file=sys.stderr,
                )
                return 1

            candidate = _build_candidate(
                topic_id=topic_id,
                topic_card_hash=_topic_card_hash(card),
                artifact=artifact.model_dump(mode="json"),
                proposed_patch=proposed_patch,
                evidence_chunk_ids=evidence_chunk_ids,
            )

            await session.rollback()

            try:
                candidate_path = _save_candidate(
                    candidate,
                    candidate_dir,
                )
            except OSError as exc:
                print(
                    f"Generated candidate could not be saved: {exc}",
                    file=sys.stderr,
                )
                return 1

            print(
                json.dumps(
                    candidate,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            print(f"Generated candidate saved; Topic was not changed: {candidate_path}")
            return 0

        patch = build_topic_card_enrichment(topic, card)
        if not patch:
            await session.rollback()
            print(
                "No enrichment changes can be built for this Topic Card.",
                file=sys.stderr,
            )
            return 1

        if apply:
            apply_topic_card_enrichment(topic, patch)
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
        print("Changes committed." if apply else "Dry run only; no changes committed.")

    return 0


async def apply_saved_topic_candidate(
    *,
    topic_id: UUID,
    candidate_id: str,
    candidate_dir: Path = DEFAULT_CANDIDATE_DIR,
) -> int:
    try:
        candidate = _load_candidate(
            candidate_id=candidate_id,
            topic_id=topic_id,
            candidate_dir=candidate_dir,
        )
    except CandidateValidationError as exc:
        print(f"Candidate rejected: {exc}", file=sys.stderr)
        return 1

    async with SessionLocal() as session:
        topic = await session.get(Topic, topic_id, with_for_update=True)
        if topic is None:
            await session.rollback()
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
            await session.rollback()
            print(
                "Topic Card has no complete curriculum context.",
                file=sys.stderr,
            )
            return 1

        if not hmac.compare_digest(_topic_card_hash(card), candidate["topic_card_hash"]):
            await session.rollback()
            print(
                "Candidate rejected: the Topic Card changed after generation.",
                file=sys.stderr,
            )
            return 1

        current_patch = build_generated_topic_card_enrichment(
            topic,
            card,
            candidate["artifact"],
            evidence_chunk_ids=candidate["evidence_chunk_ids"],
        )
        if _json_value(current_patch) != candidate["proposed_patch"]:
            await session.rollback()
            print(
                "Candidate rejected: the Topic Card changed after generation.",
                file=sys.stderr,
            )
            return 1

        apply_topic_card_enrichment(
            topic,
            candidate["proposed_patch"],
        )
        await session.commit()

    print(
        json.dumps(
            candidate,
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"Candidate {candidate_id} committed.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build Topic Card enrichment for a selected topic. "
            "The default mode is read-only. Generated enrichment is saved "
            "as a candidate and must be applied in a separate command."
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
            "Persist the built-in manual enrichment; this cannot be used with generated candidates."
        ),
    )
    candidate_mode = parser.add_mutually_exclusive_group()
    candidate_mode.add_argument(
        "--generate",
        action="store_true",
        help=(
            "Generate Topic Card enrichment with the configured provider. "
            "The candidate is saved locally and the Topic is not changed."
        ),
    )
    candidate_mode.add_argument(
        "--apply-candidate",
        metavar="CANDIDATE_ID",
        help=(
            "Validate and apply the exact saved candidate with this SHA-256 "
            "ID, without calling the generation provider."
        ),
    )
    parser.add_argument(
        "--candidate-dir",
        type=Path,
        default=DEFAULT_CANDIDATE_DIR,
        help=(f"Candidate JSON store (default: {DEFAULT_CANDIDATE_DIR})."),
    )

    args = parser.parse_args()

    if args.generate and args.apply:
        parser.error(
            "--generate cannot be combined with --apply; run --generate, "
            "then --apply-candidate CANDIDATE_ID"
        )

    if args.apply_candidate and args.apply:
        parser.error("--apply-candidate cannot be combined with --apply")

    if args.apply_candidate:
        raise SystemExit(
            asyncio.run(
                apply_saved_topic_candidate(
                    topic_id=args.topic_id,
                    candidate_id=args.apply_candidate,
                    candidate_dir=args.candidate_dir,
                )
            )
        )

    raise SystemExit(
        asyncio.run(
            enrich_topic(
                topic_id=args.topic_id,
                apply=args.apply,
                generate=args.generate,
                candidate_dir=args.candidate_dir,
            )
        )
    )


if __name__ == "__main__":
    main()
