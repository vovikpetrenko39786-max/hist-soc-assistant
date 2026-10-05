from pathlib import Path

from app.services.docx_renderer import DocxArtifactRenderer
from app.services.output_templates import OutputTemplateRegistry


def assessment(audience="teacher"):
    tasks = [{
        "number": 1,
        "instruction": "Дайте определение понятия «социальный институт».",
        "skill": "Определение",
        "difficulty": "basic",
        "points": 2,
        "student_data": None,
        "answer": "Устойчивая форма организации совместной деятельности людей." if audience == "teacher" else None,
        "criteria": "2 балла: раскрыт смысл и указан общественный характер." if audience == "teacher" else None,
    }]
    return {
        "artifact_type": "assessment",
        "title": "Социальные институты: проверочная работа",
        "grade": 10,
        "subject": "SOCIAL_STUDIES",
        "assessment_type": "check",
        "time_minutes": 15,
        "instructions": "Выполните задания самостоятельно.",
        "tasks": tasks,
        "max_points": 2,
        "grading_scale": {"5": "85-100%"},
        "common_errors_to_watch": ["Не путать институт и организацию."],
        "source_references": [],
    }


def test_template_registry():
    assert "school_clean" in OutputTemplateRegistry.names()
    assert OutputTemplateRegistry.get("school_clean").version == "1.1"


def test_teacher_docx_renders(tmp_path):
    path = tmp_path / "teacher.docx"
    DocxArtifactRenderer(OutputTemplateRegistry.get("school_clean")).render(
        assessment("teacher"), "teacher", path
    )
    assert path.exists()
    assert path.stat().st_size > 1000


def test_student_docx_renders(tmp_path):
    path = tmp_path / "student.docx"
    artifact = assessment("student")
    DocxArtifactRenderer(OutputTemplateRegistry.get("school_clean")).render(
        artifact, "student", path
    )
    assert path.exists()
    assert path.stat().st_size > 1000
