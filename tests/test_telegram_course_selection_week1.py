"""User-specific course picker contract, no private data or dynamic UUID input."""
import pytest

from telegram_bot.course_selection import (
    choices_for_user,
    course_kwargs,
    get_selected_choice,
    parse_course_bindings,
)

UID = "6fa13ae0-473e-45ea-abfc-1eb0b224e5dd"


def cfg():
    return parse_course_bindings(
        '{"123":{"9Б-Общество":{"class_course_id":"' + UID + '",'
        '"source_key":"MEDVEDEV-9","label":"9-Б Обществознание"}},"456":{}}'
    )


def test_unconfigured_user_has_no_courses():
    assert parse_course_bindings(None) == {}
    assert parse_course_bindings("  ") == {}
    assert choices_for_user(cfg(), 999) == {}
    assert choices_for_user(cfg(), None) == {}


def test_per_user_selection_is_scoped_and_normalized():
    config = cfg()
    c = get_selected_choice(config, 123, "9б-общество")
    assert c is not None
    assert c.label == "9-Б Обществознание"
    assert get_selected_choice(config, 456, "9Б-Общество") is None
    assert get_selected_choice(config, 999, "9б-общество") is None
    assert get_selected_choice(config, 123, str(c.class_course_id)) is None


def test_propagation_only_allows_trusted_course_and_source():
    c = get_selected_choice(cfg(), 123, "9б-общество")
    assert course_kwargs(c) == {"class_course_id": UID, "source_key": "MEDVEDEV-9"}
    assert course_kwargs(None) == {}


@pytest.mark.parametrize("raw", [
    "not json", "[]", '{"-1":{}}', '{"0":{}}', '{"123":[]}',
    '{"123":{"course":{"class_course_id":"not-a-uuid"}}}',
    '{"123":{"9a":{"class_course_id":"00000000-0000-0000-0000-000000000000"}}}',
    '{"123":{"9a":{"class_course_id":"' + UID + '","source_key":"  "}}}',
    '{"123":{"9a":{"class_course_id":"' + UID + '","extra":1}}}',
    '{"123":{"9a":{"class_course_id":"' + UID + '"},"9A":{"class_course_id":"' + UID + '"}}}',
    '{"123":{"x":{"class_course_id":"' + UID + '"}}}',
])
def test_bad_bindings_are_rejected(raw):
    with pytest.raises(ValueError):
        parse_course_bindings(raw)
