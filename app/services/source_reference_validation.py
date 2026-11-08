"""Validate generated citations against the exact retrieval manifest.

This module is deliberately independent of database access and network calls.
"""
from __future__ import annotations


def validate_source_references(references, manifest: list[dict]) -> list[str]:
    """Return validation codes; never trust an LLM-provided source identity.

    A duplicate chunk id in the manifest is ambiguous and cannot be cited.
    Optional metadata is checked only when the manifest has an authoritative value.
    """
    chunks: dict[str, list[dict]] = {}
    for entry in manifest:
        chunk_id = entry.get("chunk_id")
        if chunk_id is not None:
            chunks.setdefault(str(chunk_id), []).append(entry)

    violations: list[str] = []
    for ref in references:
        matches = chunks.get(str(ref.chunk_id), [])
        if len(matches) != 1:
            violations.append("missing_or_ambiguous_chunk")
            continue
        entry = matches[0]
        if not entry.get("source_id") and not entry.get("source_key") and not entry.get("url"):
            violations.append("unidentified_source")
            continue
        for field in ("source_id", "source_key", "url"):
            expected = entry.get(field)
            actual = getattr(ref, field, None)
            if expected is not None and str(actual) != str(expected):
                violations.append(f"{field}_mismatch")
        for field in ("page_pdf_start", "page_pdf_end", "page_print_start", "page_print_end"):
            expected = entry.get(field)
            if expected is not None and getattr(ref, field, None) != expected:
                violations.append(f"{field}_mismatch")
        if bool(getattr(ref, "quote_safe", False)) and not bool(entry.get("quote_safe", False)):
            violations.append("unsafe_quote_claim")
    return violations
