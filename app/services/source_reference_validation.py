"""Validate generated citations against the exact retrieval manifest.

This module is deliberately independent of database access and network calls.
"""
from __future__ import annotations


def validate_source_references(references, manifest: list[dict]) -> list[str]:
    """Return validation codes; never trust an LLM-provided source identity.

    A duplicate chunk id in the manifest is ambiguous and cannot be cited.
    Missing metadata is authoritative too: generated citations must not invent
    URLs, sections, or page numbers that retrieval did not provide.
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
            if expected is None:
                if actual not in (None, ""):
                    violations.append(f"{field}_mismatch")
            elif str(actual) != str(expected):
                violations.append(f"{field}_mismatch")
        expected_title = entry.get("title") or entry.get("source_title")
        if (
            expected_title is not None
            and str(getattr(ref, "title", "")) != str(expected_title)
        ):
            violations.append("title_mismatch")
        expected_section = entry.get("section")
        actual_section = getattr(ref, "section", None)
        if expected_section is None:
            if actual_section not in (None, ""):
                violations.append("section_mismatch")
        elif str(actual_section) != str(expected_section):
            violations.append("section_mismatch")
        for field in ("page_pdf_start", "page_pdf_end", "page_print_start", "page_print_end"):
            expected = entry.get(field)
            if getattr(ref, field, None) != expected:
                violations.append(f"{field}_mismatch")
        if bool(getattr(ref, "quote_safe", False)) and not bool(entry.get("quote_safe", False)):
            violations.append("unsafe_quote_claim")
    return violations
