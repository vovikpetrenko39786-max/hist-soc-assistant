from __future__ import annotations

from app.schemas.generation import LessonArtifact


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

        # Source grounding: references must be a subset of manifest.
        allowed_chunks = {str(item["chunk_id"]): item for item in source_manifest}
        invalid_refs = [
            ref for ref in artifact.source_references
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
            fields = [
                "page_pdf_start", "page_pdf_end",
                "page_print_start", "page_print_end",
            ]
            for field in fields:
                if getattr(ref, field) != manifest.get(field):
                    page_mismatches.append((str(ref.chunk_id), field))
        add(
            "page_grounding",
            not page_mismatches,
            "error",
            "Все страницы взяты из retrieval manifest."
            if not page_mismatches
            else f"Есть расхождения страниц: {page_mismatches[:5]}",
        )

        required_concepts = {
            item["term"].casefold()
            for item in topic_card.get("concepts", [])
            if item.get("importance") == "required"
        }
        artifact_concepts = {item.casefold() for item in artifact.key_concepts}
        concept_coverage = (
            1.0 if not required_concepts
            else len(required_concepts & artifact_concepts) / len(required_concepts)
        )
        add(
            "required_concepts",
            concept_coverage >= 0.5,
            "warning",
            f"Покрытие обязательных понятий: {concept_coverage:.0%}.",
        )

        errors = [x for x in checks if not x["passed"] and x["severity"] == "error"]
        warnings = [x["message"] for x in checks if not x["passed"] and x["severity"] == "warning"]

        passed_weight = sum(
            1 for x in checks if x["passed"]
        )
        score = round(100 * passed_weight / max(1, len(checks)))

        return {
            "passed": not errors,
            "score": score,
            "checks": checks,
            "warnings": warnings,
        }
