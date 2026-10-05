from app.schemas.generation import LessonArtifact
from app.services.quality_gate import LessonQualityGate


def source_checks(artifact: dict, manifest: list[dict]):
    allowed = {str(x["chunk_id"]): x for x in manifest}
    refs = artifact.get("source_references", []) or []
    invalid = [x for x in refs if str(x["chunk_id"]) not in allowed]
    mismatches = []
    for ref in refs:
        src = allowed.get(str(ref["chunk_id"]))
        if not src: continue
        for f in ("page_pdf_start","page_pdf_end","page_print_start","page_print_end"):
            if ref.get(f) != src.get(f): mismatches.append((str(ref["chunk_id"]), f))
    return [
        {"code":"source_subset","passed":not invalid,"severity":"error","message":"Все ссылки подтверждены retrieval manifest." if not invalid else f"Неподтверждённых ссылок: {len(invalid)}."},
        {"code":"page_grounding","passed":not mismatches,"severity":"error","message":"Страницы подтверждены retrieval manifest." if not mismatches else f"Расхождения страниц: {mismatches[:5]}"},
    ]


class PedagogyQualityGate:
    def evaluate(self, artifact_type, teacher, student, topic_card, manifest):
        if artifact_type == "lesson":
            payload = dict(teacher); payload.pop("artifact_type", None)
            return LessonQualityGate().evaluate(LessonArtifact.model_validate(payload), topic_card or {}, manifest)
        checks = source_checks(teacher, manifest)
        def add(code, passed, message): checks.append({"code":code,"passed":bool(passed),"severity":"error","message":message})
        if artifact_type == "assessment":
            tasks = teacher.get("tasks", []); points = sum(int(x.get("points", 0)) for x in tasks)
            add("has_tasks", bool(tasks), "Есть задания.")
            add("points_match", points == teacher.get("max_points"), f"Сумма баллов {points}; максимум {teacher.get('max_points')}.")
            add("teacher_has_keys", all(x.get("answer") is not None for x in tasks), "Учительская версия содержит ответы.")
            if student: add("student_no_keys", all(x.get("answer") is None and x.get("criteria") is None for x in student.get("tasks", [])), "Версия ученика не содержит ключей.")
        elif artifact_type == "worksheet":
            tasks = [x for s in teacher.get("sections", []) for x in s.get("tasks", [])]
            add("has_tasks", bool(tasks), "Есть задания.")
            if student:
                st = [x for s in student.get("sections", []) for x in s.get("tasks", [])]
                add("student_no_keys", all(x.get("answer") is None for x in st), "Версия ученика не содержит ответов.")
        elif artifact_type == "homework":
            add("time_defined", int(teacher.get("estimated_minutes", 0)) > 0, "Время определено.")
            add("success_criteria", bool(teacher.get("success_criteria")), "Есть критерии успеха.")
            if student: add("student_no_teacher_note", student.get("teacher_note") is None, "В student version нет служебной заметки.")
        elif artifact_type == "idea_enhancement":
            labels = {x.get("label") for x in teacher.get("options", [])}
            add("preserves_core", bool(teacher.get("preserve_core")), "Ядро идеи сохраняется.")
            add("three_options", {"minimal","optimal","bold"}.issubset(labels), "Есть три уровня реализации.")
            add("recommended_option", teacher.get("recommended_option") in labels, "Есть рекомендуемый вариант.")
        errors = [x for x in checks if not x["passed"] and x["severity"] == "error"]
        score = round(100 * sum(1 for x in checks if x["passed"]) / max(1, len(checks)))
        return {"passed":not errors,"score":score,"checks":checks,"warnings":[]}
