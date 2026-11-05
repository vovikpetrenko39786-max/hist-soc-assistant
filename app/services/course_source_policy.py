"""Pick the source linked to the class course, rather than guessing a book."""
from __future__ import annotations


def select_primary_source(
    requested_source_key: str | None,
    primary_source_key: str | None,
    use_course_materials: bool,
) -> str | None:
    """No silent cross-textbook substitution for a selected course.

    Explicit keys may be used if the class has no saved primary book.
    Informational/general requests do not inherit the course's textbook.
    """
    if (requested_source_key and primary_source_key
            and requested_source_key != primary_source_key):
        raise ValueError("Selected textbook conflicts with saved course textbook")
    if requested_source_key:
        return requested_source_key
    if use_course_materials and primary_source_key:
        return primary_source_key
    return None
