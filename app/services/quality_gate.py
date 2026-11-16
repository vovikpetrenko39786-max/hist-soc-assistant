from __future__ import annotations

from app.schemas.generation import LessonArtifact
from app.services.source_reference_validation import validate_source_references


class LessonQualityGate:
    def evaluate(
        self,
        artifact: LessonArtifact,
        topic_card: dict,
        source_manifest: list[dict],
    ) -> dict:
        checks = []

        def add(code, passed, severity, message):
            checks.append(
                {
                    "code": code,
                    "passed": bool(passed),
                    "severity": severity,
                    "message": message,
                }
            )

        total_minutes = sum(step.minutes for step in artifact.timeline)
        add(
            "timing_exact",
            total_minutes == artifact.duration_minutes,
            "error",
            f"Сумма этапов {total_minutes} мин.; заявлено {artifact.duration_minutes} мин.",
        )

        add(
            "has_measurable_outcomes",
            bool(artifact.measurable_outcomes),
            "error",
            "Есть измеримые результаты урока."
            if artifact.measurable_outcomes
            else "Нет измеримых результатов.",
        )

        student_actions = " ".join(step.student_action for step in artifact.timeline).casefold()
        add(
            "student_activity",
            len(student_actions) >= 80,
            "error",
            "Деятельность ученика описана содержательно."
            if len(student_actions) >= 80
            else "Недостаточно описана деятельность ученика.",
        )

        add(
            "evidence_of_learning",
            any(step.evidence_of_learning for step in artifact.timeline),
            "error",
            "Есть наблюдаемое свидетельство обучения."
            if any(step.evidence_of_learning for step in artifact.timeline)
            else "Нет точки контроля понимания.",
        )

        add(
            "formative_check",
            bool(artifact.formative_check),
            "error",
            "Предусмотрена формирующая проверка."
            if artifact.formative_check
            else "Отсутствует формирующая проверка.",
        )

        add(
            "reflection",
            bool(artifact.reflection),
            "warning",
            "Есть содержательная рефлексия."
            if artifact.reflection
            else "Рефлексия отсутствует.",
        )

        alignment = artifact.fgos_alignment
        alignment_complete = all(
            (
                alignment.subject_results,
                alignment.meta_subject_results,
                alignment.personal_results,
                alignment.learning_activities,
                alignment.assessment_evidence,
            )
        )
        add(
            "fgos_operational_alignment",
            alignment_complete,
            "error",
            "Результаты связаны с деятельностью и наблюдаемой проверкой."
            if alignment_complete
            else "Методическая привязка результатов, деятельности и проверки неполна.",
        )

        planned_results = {
            str(item).strip().casefold() for item in artifact.measurable_outcomes
        }
        aligned_results = {
            str(item).strip().casefold() for item in alignment.subject_results
        }
        add(
            "subject_result_alignment",
            bool(planned_results & aligned_results),
            "error",
            "Предметный результат согласован с планом урока."
            if planned_results & aligned_results
            else "Предметные результаты в методической привязке расходятся с планом урока.",
        )

        narrative_text = " ".join(
            str(value)
            for block in artifact.teacher_narrative
            for value in (
                block.teacher_script
                + block.student_prompts
                + block.board_notes
                + block.attention_points
            )
        ).strip()
        narrative_ok = len(artifact.teacher_narrative) >= 3 and len(narrative_text) >= 1200
        add(
            "professional_teacher_narrative",
            narrative_ok,
            "error",
            f"Рассказ учителя содержателен: {len(artifact.teacher_narrative)} блока, {len(narrative_text)} знаков."
            if narrative_ok
            else "Нужен подробный предметный рассказ учителя минимум в трёх смысловых блоках.",
        )

        questions_ok = (
            len(artifact.anticipated_student_questions) >= 3
            and all(
                len(item.short_answer.strip()) >= 20
                and len(item.expanded_answer.strip()) >= 60
                and len(item.teaching_note.strip()) >= 20
                for item in artifact.anticipated_student_questions
            )
        )
        add(
            "anticipated_student_questions",
            questions_ok,
            "error",
            "Предусмотрены реалистичные вопросы учеников, ответы и подсказки учителю."
            if questions_ok
            else "Недостаточно проработаны возможные вопросы учеников и ответы на них.",
        )

        misconception_ok = bool(artifact.misconception_support) and all(
            item.diagnostic_question.strip()
            and item.correction.strip()
            and item.example_or_counterexample.strip()
            for item in artifact.misconception_support
        )
        add(
            "misconception_support",
            misconception_ok,
            "error",
            "Есть диагностика и коррекция типичных ошибок."
            if misconception_ok
            else "Нет полноценной поддержки по типичным ошибкам.",
        )

        required_variants = {
            "teacher_explanation", "textbook_independent", "group_work"
        }
        present_variants = {item.approach for item in artifact.lesson_variants}
        variants_ok = required_variants.issubset(present_variants) and all(
            len(item.steps) >= 4
            and bool(item.evidence_of_learning.strip())
            and bool(item.risks_and_mitigation)
            for item in artifact.lesson_variants
        )
        add(
            "three_lesson_variants",
            variants_ok,
            "error",
            "Есть три полноценных варианта проведения с общей проверкой результата."
            if variants_ok
            else "Нужны три варианта: объяснение, самостоятельная работа с учебником и групповая работа.",
        )

        notebook_ok = len(artifact.notebook) >= 2 and all(
            str(item).strip() for item in artifact.notebook
        )
        add(
            "notebook_ready",
            notebook_ok,
            "error",
            "Опорная запись для тетради готова."
            if notebook_ok
            else "Запись в тетрадь должна содержать минимум два содержательных пункта.",
        )

        add(
            "methodical_notes",
            len(artifact.methodical_notes) >= 2,
            "error",
            "Есть методические акценты для проведения урока."
            if len(artifact.methodical_notes) >= 2
            else "Недостаточно методических акцентов для учителя.",
        )

        # Preserve the established quality-report contract while the stricter
        # validator below checks source identity and quote permissions too.
        allowed_chunks = {
            str(item.get("chunk_id")): item
            for item in source_manifest
            if item.get("chunk_id")
            and (item.get("source_id") or item.get("source_key") or item.get("url"))
        }
        invalid_refs = [
            ref
            for ref in artifact.source_references
            if str(ref.chunk_id) not in allowed_chunks
        ]
        add(
            "source_subset",
            not invalid_refs,
            "error",
            "Все source references происходят из retrieval manifest."
            if not invalid_refs
            else f"Найдены {len(invalid_refs)} неподтверждённых source reference.",
        )

        page_mismatches = []
        for ref in artifact.source_references:
            manifest = allowed_chunks.get(str(ref.chunk_id))
            if not manifest:
                continue
            for field in (
                "page_pdf_start",
                "page_pdf_end",
                "page_print_start",
                "page_print_end",
            ):
                if (
                    manifest.get(field) is not None
                    and getattr(ref, field) != manifest[field]
                ):
                    page_mismatches.append((str(ref.chunk_id), field))
        add(
            "page_grounding",
            not page_mismatches,
            "error",
            "Все страницы взяты из retrieval manifest."
            if not page_mismatches
            else f"Есть расхождения страниц: {page_mismatches[:5]}",
        )

        # Reject forged source identity, page numbers, quote permissions and
        # ambiguous retrieval chunk ids before considering an artifact grounded.
        source_violations = validate_source_references(
            artifact.source_references, source_manifest
        )
        add(
            "source_reference_integrity",
            not source_violations,
            "error",
            "Ссылки подтверждены retrieval manifest."
            if not source_violations
            else f"Некорректные ссылки на источники: {len(source_violations)}.",
        )

        required_concepts = {
            item["term"].casefold().strip()
            for item in topic_card.get("concepts", [])
            if item.get("importance") == "required"
        }
        artifact_concepts = [
            item.casefold().strip()
            for item in artifact.key_concepts
        ]

        def concept_is_covered(required: str) -> bool:
            for candidate in artifact_concepts:
                if candidate == required:
                    return True
                if candidate.startswith(required):
                    remainder = candidate[len(required):]
                    if not remainder or not remainder[0].isalnum():
                        return True
            return False

        covered_concepts = {
            concept for concept in required_concepts
            if concept_is_covered(concept)
        }

        concept_coverage = (
            1.0 if not required_concepts
            else len(covered_concepts) / len(required_concepts)
        )
        add(
            "required_concepts",
            concept_coverage >= 0.5,
            "warning",
            f"Покрытие обязательных понятий: {concept_coverage:.0%}.",
        )

        artifact_text = str(artifact.model_dump(mode="json")).casefold()
        generic_markers = (
            "найти в учебнике",
            "найдите в учебнике",
            "фрагмент учебника",
            "выбранного фрагмента",
            "одного из обществ",
            "материал урока",
            "по материалу учебника",
            "из учебника",
        )
        generic_hits = sum(artifact_text.count(x) for x in generic_markers)
        specificity_ok = generic_hits <= 3
        add(
            "content_specificity",
            specificity_ok,
            "warning",
            f"Предметная конкретика: generic_hits={generic_hits}.",
        )


        if source_manifest:
            add(
                "source_grounding_presence",
                bool(artifact.source_references),
                "error",
                "Источники retrieval использованы."
                if artifact.source_references
                else "Источники найдены retrieval, но урок на них не ссылается.",
            )
        else:
            add(
                "source_grounding_presence",
                False,
                "warning",
                "Retrieval не дал содержательных источников.",
            )

        errors = [x for x in checks if not x["passed"] and x["severity"] == "error"]
        warnings = [x["message"] for x in checks if not x["passed"] and x["severity"] == "warning"]

        passed_weight = sum(
            1 for x in checks if x["passed"]
        )
        score = round(100 * passed_weight / max(1, len(checks)))
        if not source_manifest:
            score = min(score, 85)
        if not specificity_ok:
            score = min(score, 75)

        return {
            "passed": not errors,
            "score": score,
            "checks": checks,
            "warnings": warnings,
        }
