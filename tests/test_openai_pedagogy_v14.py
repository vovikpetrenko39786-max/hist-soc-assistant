from app.services.openai_pedagogy import _student_from_teacher


def test_assessment_student_strips_keys():
    teacher = {
        "artifact_type": "assessment",
        "tasks": [{"answer": "A", "criteria": "C"}],
        "common_errors_to_watch": ["x"],
    }
    student = _student_from_teacher("assessment", teacher)
    assert student["tasks"][0]["answer"] is None
    assert student["tasks"][0]["criteria"] is None
    assert student["common_errors_to_watch"] == []


def test_worksheet_student_strips_keys():
    teacher = {
        "artifact_type": "worksheet",
        "sections": [{"tasks": [{"answer": "A", "criteria": "C"}]}],
        "teacher_key": ["secret"],
    }
    student = _student_from_teacher("worksheet", teacher)
    assert student["sections"][0]["tasks"][0]["answer"] is None
    assert student["teacher_key"] == []


def test_lesson_has_no_student_version():
    assert _student_from_teacher("lesson", {"artifact_type": "lesson"}) is None
