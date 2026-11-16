"""Course/source grounding: no silent textbook switching."""
import pytest

from app.services.course_source_policy import select_primary_source


def test_course_uses_saved_primary_textbook():
    assert select_primary_source(None, "BOOK-FOR-9B", True) == "BOOK-FOR-9B"


def test_external_information_does_not_inherit_primary_book():
    assert select_primary_source(None, "BOOK-FOR-9B", False) is None


def test_explicit_matching_source_is_accepted():
    assert select_primary_source("BOOK-FOR-9B", "BOOK-FOR-9B", True) == "BOOK-FOR-9B"


def test_explicit_mismatch_is_rejected():
    with pytest.raises(ValueError, match="conflicts"):
        select_primary_source("BOOK-FOR-10A", "BOOK-FOR-9B", True)


def test_unconfigured_course_book_remains_non_strict_unless_explicit():
    assert select_primary_source(None, None, True) is None
    assert select_primary_source("BOOK-SELECTED", None, True) == "BOOK-SELECTED"
