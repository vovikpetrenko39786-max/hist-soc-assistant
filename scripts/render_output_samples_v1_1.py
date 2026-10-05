import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.docx_renderer import DocxArtifactRenderer
from app.services.output_templates import OutputTemplateRegistry
from app.services.pdf_export import PdfExporter


def artifact(audience):
    tasks = [
        {
            "number": 1,
            "instruction": "Дайте определение понятия «социальный институт».",
            "points": 2,
            "answer": "Социальный институт - исторически сложившаяся устойчивая форма организации совместной деятельности людей." if audience == "teacher" else None,
            "criteria": "2 балла: раскрыт смысл понятия; 1 балл: дан частично верный ответ." if audience == "teacher" else None,
        },
        {
            "number": 2,
            "instruction": "Назовите два признака социального института и поясните один из них.",
            "points": 3,
            "answer": "Например: устойчивость; наличие норм и ролей. Пояснение должно раскрывать один признак." if audience == "teacher" else None,
            "criteria": "1+1 балл за два признака, 1 балл за корректное пояснение." if audience == "teacher" else None,
        },
        {
            "number": 3,
            "instruction": "Анна поступила в университет, посещает занятия по расписанию и выполняет требования образовательной программы. Какой социальный институт иллюстрирует ситуация? Объясните ответ.",
            "points": 3,
            "answer": "Образование. В ситуации показаны устойчивые нормы, роли и деятельность, связанные с передачей знаний и социализацией." if audience == "teacher" else None,
            "criteria": "1 балл за институт, до 2 баллов за содержательное объяснение." if audience == "teacher" else None,
        },
    ]
    return {
        "artifact_type": "assessment",
        "title": "Социальные институты: мини-проверочная",
        "grade": 10,
        "subject": "SOCIAL_STUDIES",
        "assessment_type": "mini_practice",
        "time_minutes": 15,
        "instructions": "Работайте самостоятельно. В заданиях с объяснением используйте предметные понятия.",
        "tasks": tasks,
        "max_points": 8,
        "grading_scale": {"5": "7-8", "4": "5-6", "3": "3-4", "2": "0-2"},
        "common_errors_to_watch": [
            "Путать социальный институт с конкретной организацией.",
            "Приводить пример без объяснения связи с понятием.",
        ],
        "source_references": [],
    }


def main():
    out = Path('/mnt/data/output_layer_v1_1_samples')
    out.mkdir(parents=True, exist_ok=True)
    renderer = DocxArtifactRenderer(OutputTemplateRegistry.get('school_clean'))
    for audience in ('teacher', 'student'):
        docx = out / f'assessment_{audience}.docx'
        pdf = out / f'assessment_{audience}.pdf'
        renderer.render(artifact(audience), audience, docx)
        PdfExporter().convert_docx(docx, pdf)
        print(docx)
        print(pdf)


if __name__ == '__main__':
    main()
