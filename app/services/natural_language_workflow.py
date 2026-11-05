from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass

from app.models.entities import GenerationRun
from app.schemas.output import OutputRenderRequest
from app.schemas.pedagogy import (
    AssessmentSpec,
    HomeworkSpec,
    PedagogyGenerationRequest,
    WorksheetSpec,
)
from app.schemas.workflow import (
    NaturalWorkflowRequest,
    ParsedArtifact,
    WorkflowPlan,
)
from app.services.course_source_policy import select_primary_source
from app.services.memory import MemoryService
from app.services.output_service import OutputRenderError, OutputService
from app.services.pedagogy_generation import (
    PedagogyGenerationError,
    PedagogyGenerationService,
)

logger = logging.getLogger(__name__)

_ARTIFACT_PATTERNS = {
    "lesson": (
        "урок", "конспект", "сценарий урока", "провести урок",
    ),
    "assessment": (
        "провероч", "самостоятель", "контрольн", "тест", "диагностик",
    ),
    "worksheet": (
        "рабочий лист", "рабочего листа", "карточк", "раздатк",
    ),
    "homework": (
        "домашнее задание", "домашку", "дз", "дневник.ру",
    ),
    "idea_enhancement": (
        "улучши идею", "доработай идею", "идея урока", "хочу сделать",
        "как реализовать идею",
    ),
}

_SUBJECT_PATTERNS = {
    "SOCIAL_STUDIES": ("обществозн", "общество"),
    "HISTORY": ("истори",),
    "INDIVIDUAL_PROJECT": ("индивидуальн", "проект"),
}

_STOP_TOPIC_WORDS = {
    "сделай", "подготовь", "создай", "нужно", "мне", "пожалуйста",
    "полноценный", "подробный", "подробно", "урок", "рабочий", "лист",
    "проверочную", "проверочная", "самостоятельную", "контрольную",
    "домашнее", "задание", "двух", "версиях", "версии", "word", "ворд",
    "docx", "pdf", "сразу", "учитель", "ученик", "для", "класс",
}


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def _normalize_topic(text: str) -> str | None:
    text = re.sub(r"\s+", " ", text).strip(" ,.;:—–-")
    if not text:
        return None
    words = text.split()
    while words and words[0].casefold() in _STOP_TOPIC_WORDS:
        words.pop(0)
    while words and words[-1].casefold() in _STOP_TOPIC_WORDS:
        words.pop()
    result = " ".join(words).strip(" ,.;:—–-")
    return result or None


class NaturalLanguageParser:
    def parse(self, request: NaturalWorkflowRequest) -> WorkflowPlan:
        raw = request.message.strip()
        low = raw.casefold()
        notes: list[str] = []
        confidence_parts: list[float] = []

        # Subject.
        subject = None
        if "индивидуальн" in low and "проект" in low:
            subject = "INDIVIDUAL_PROJECT"
        else:
            for code, needles in _SUBJECT_PATTERNS.items():
                if _has_any(low, needles):
                    subject = code
                    break
        confidence_parts.append(1.0 if subject else 0.0)

        # Grade/class.
        grade = None
        class_label = None
        match = re.search(
            r"(?<!\d)(5|6|7|8|9|10|11)\s*(?:[-–—]\s*([а-яa-z])(?![а-яa-z]))?\s*(?:класс(?:а|е|у|ом)?|кл\.?)?",
            low,
        )
        if match:
            grade = int(match.group(1))
            letter = match.group(2)
            class_label = f"{grade}-{letter.upper()}" if letter else None
        confidence_parts.append(1.0 if grade else 0.0)

        # Level.
        level = None
        if any(x in low for x in ("углуб", "профиль", "профильный")):
            level = "advanced"
        elif any(x in low for x in ("базовый", "база", "базовом уровне")):
            level = "basic"

        # Mode.
        mode = "practical"
        if any(x in low for x in ("полноцен", "подробно", "подробный", "полный")):
            mode = "full"
        if any(x in low for x in ("открытый урок", "для администрации", "аттестаци")):
            mode = "formal"
        if any(x in low for x in (
            "ничего не готов", "ничего не подготовил", "через 10 минут",
            "через 20 минут", "срочно урок",
        )):
            mode = "emergency"

        # Duration.
        duration_minutes = None
        m = re.search(r"(?:на\s*)?(\d{2,3})\s*(?:минут|мин\.?)", low)
        if m:
            duration_minutes = int(m.group(1))
        elif "урок" in low:
            duration_minutes = 45

        # Artifacts: allow multiple from one phrase.
        artifact_types: list[str] = []
        for artifact_type, patterns in _ARTIFACT_PATTERNS.items():
            if _has_any(low, patterns):
                artifact_types.append(artifact_type)

        if not artifact_types:
            # Teacher-facing informational / analytical request.
            # Explicit lesson / assessment / worksheet / homework detection
            # above always has higher priority.
            info_markers = (
                "памятк",
                "что изменил",
                "изменени",
                "что нового",
                "сравни",
                "сравнение",
                "обзор",
                "объясни",
                "расскажи",
                "проанализируй",
                "анализ",
                "справк",
                "егэ",
                "огэ",
                "фипи",
                "демоверс",
                "кодифик",
                "спецификац",
            )

            informational_request = any(
                marker in low for marker in info_markers
            )

            if informational_request:
                artifact_types = ["informational"]

                # Exam requests have deterministic grade context.
                if "егэ" in low:
                    grade = grade or 11
                    class_label = class_label or "11"
                    level = "exam"
                elif "огэ" in low:
                    grade = grade or 9
                    class_label = class_label or "9"
                    level = "exam"

                notes.append(
                    "Информационно-аналитический запрос направлен "
                    "в teacher-facing режим."
                )
                confidence_parts.append(0.90)

            else:
                # Preserve the old default for ordinary teaching requests.
                artifact_types = ["lesson"]
                notes.append(
                    "Тип материала не указан явно; выбран lesson по умолчанию."
                )
                confidence_parts.append(0.55)
        else:
            confidence_parts.append(1.0)

        # Normalize IDEA Enhancer intent.
        #
        # Mentioning the word "урок" inside "идея урока" must not
        # automatically request a full lesson. A lesson is added only when
        # the user explicitly asks to create/prepare/build one.
        idea_improvement_request = any(
            x in low
            for x in (
                "улучши идею",
                "улучшить идею",
                "доработай идею",
                "доработать идею",
                "развить идею",
                "развей идею",
                "помоги её улучшить",
                "помоги ее улучшить",
                "есть идея урока",
                "идея для урока",
            )
        )

        explicit_lesson_build = any(
            x in low
            for x in (
                "подготовь урок",
                "подготовить урок",
                "составь урок",
                "составить урок",
                "разработай урок",
                "разработать урок",
                "создай урок",
                "создать урок",
                "сделай урок",
                "сделать урок",
                "план урока",
                "конспект урока",
                "на основе идеи подготовь урок",
                "на её основе подготовь урок",
                "на ее основе подготовь урок",
            )
        )

        if "informational" not in artifact_types and idea_improvement_request:
            if explicit_lesson_build:
                artifact_types = ["idea_enhancement", "lesson"]
            else:
                artifact_types = ["idea_enhancement"]

        # Audience.
        both = any(x in low for x in (
            "две версии", "двух версиях", "учитель и ученик",
            "ученика и учителя", "учительская и ученическая",
            "для учителя и ученика",
        ))
        only_student = any(x in low for x in ("только для ученика", "версия ученика"))
        only_teacher = any(x in low for x in ("только для учителя", "версия учителя"))

        artifacts: list[ParsedArtifact] = []
        for artifact_type in artifact_types:
            if both and artifact_type in {"assessment", "worksheet", "homework"}:
                audience = "both"
            elif only_student:
                audience = "student"
            elif only_teacher:
                audience = "teacher"
            else:
                # Lessons and IDEA Enhancer are teacher-facing by default.
                audience = "teacher"
            artifacts.append(ParsedArtifact(artifact_type=artifact_type, audience=audience))

        # Formats.
        formats: list[str] = []
        if any(x in low for x in ("word", "ворд", "docx")):
            formats.append("docx")
        if "pdf" in low:
            formats.append("pdf")
        if not formats and request.default_formats:
            formats = list(request.default_formats)

        # Assessment options.
        assessment_task_count = None
        m = re.search(r"(\d{1,2})\s*(?:задани|вопрос)", low)
        if m:
            assessment_task_count = int(m.group(1))

        assessment_max_points = None
        m = re.search(r"(?:максимум|max|на)\s*(\d{1,3})\s*бал", low)
        if m:
            assessment_max_points = int(m.group(1))

        # Source / knowledge policy.
        strict_source = any(x in low for x in (
            "только по учебнику", "строго по учебнику", "именно по учебнику",
            "точная цитата", "на какой странице",
        ))

        if any(x in low for x in ("не ищи в интернете", "только библиотека", "без интернета")):
            knowledge_policy = "library_only"
            web_allowed = False
        elif any(x in low for x in (
            "найди в интернете", "проверь в интернете", "актуальные данные",
            "последние данные", "свежие данные",
        )):
            knowledge_policy = "official_web_first"
            web_allowed = request.allow_web_fallback
        else:
            knowledge_policy = "library_first"
            web_allowed = request.allow_web_fallback

        # A source_key is an explicit choice of evidence source even if the
        # prompt does not contain the words "only from this textbook".
        # Empty/whitespace identifiers are not valid selections.
        selected_source = (request.source_key or "").strip() or None
        strict_source = strict_source or bool(selected_source)
        if strict_source:
            knowledge_policy = "library_only"
            web_allowed = False

        # Topic extraction.
        topic = self._extract_topic(raw, low, subject, grade)
        if topic:
            confidence_parts.append(1.0)
        else:
            confidence_parts.append(0.0)
            if not any(x in artifact_types for x in ("idea_enhancement", "informational")):
                notes.append("Не удалось надёжно выделить тему из свободного текста.")

        confidence = sum(confidence_parts) / len(confidence_parts)

        return WorkflowPlan(
            original_message=raw,
            subject=subject,
            grade=grade,
            class_label=class_label,
            level=level,
            topic=topic,
            duration_minutes=duration_minutes,
            mode=mode,
            artifacts=artifacts,
            formats=formats,
            template_name=request.template_name,
            strict_source=strict_source,
            source_key=selected_source,
            assessment_task_count=assessment_task_count,
            assessment_max_points=assessment_max_points,
            knowledge_policy=knowledge_policy,
            web_fallback_allowed=web_allowed,
            parser_confidence=round(confidence, 3),
            notes=notes,
        )

    def _extract_topic(
        self,
        raw: str,
        low: str,
        subject: str | None,
        grade: int | None,
    ) -> str | None:
        # 1. Explicit "тема: ..."
        m = re.search(
            r"(?:тема|по теме)\s*[:—–-]?\s*[«\"]?([^»\"\n.]+)[»\"]?",
            raw,
            flags=re.IGNORECASE,
        )
        if m:
            candidate = re.split(
                r"\b(?:сделай|подготовь|создай|нужно|урок|рабочий лист|проверочн)\b",
                m.group(1),
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            return _normalize_topic(candidate)

        # 2. Explicit action followed by a colon:
        # "Сделай урок: социальные институты".
        m = re.search(
            r"(?:сделай|подготовь|создай|составь|разработай)\s+"
            r"(?:урок|конспект|рабочий лист|проверочн\w*|домашнее задание)\s*"
            r"[:—–-]\s*[«\"]?([^»\"\n.]+)[»\"]?",
            raw,
            flags=re.IGNORECASE,
        )
        if m:
            return _normalize_topic(m.group(1))

        # 3. Quoted phrase is often the topic.
        quoted = re.findall(r"[«\"]([^»\"]{3,120})[»\"]", raw)
        for item in quoted:
            if not any(x in item.casefold() for x in ("учитель", "ученик", "word", "pdf")):
                return _normalize_topic(item)

        # 4. Comma-separated teacher shorthand:
        # "10 класс, обществознание, социальные институты. Сделай..."
        first_sentence = re.split(r"[.!?]\s*", raw, maxsplit=1)[0]
        parts = [p.strip() for p in re.split(r"[,;]", first_sentence) if p.strip()]
        cleaned = []
        for part in parts:
            p = part
            p_low = p.casefold()
            if re.search(r"(?<!\d)(5|6|7|8|9|10|11)\s*(?:класс|кл\.?)?", p_low):
                continue
            if any(x in p_low for x in ("обществозн", "истори", "индивидуальн")):
                continue
            if any(k in p_low for k in (
                "сделай", "подготовь", "создай", "урок", "рабочий лист",
                "провероч", "самостоятель", "контрольн", "домашн",
            )):
                p = re.split(
                    r"\b(?:сделай|подготовь|создай|урок|рабочий лист|провероч\w*|самостоятель\w*|контрольн\w*|домашн\w*)\b",
                    p,
                    maxsplit=1,
                    flags=re.IGNORECASE,
                )[0]
            p = _normalize_topic(p)
            if p:
                cleaned.append(p)
        if cleaned:
            # Prefer first plausible content phrase after class/subject.
            return cleaned[0]

        # 5. Subject-following phrase:
        subject_words = []
        if subject == "SOCIAL_STUDIES":
            subject_words = ["обществознание", "обществознания", "общество"]
        elif subject == "HISTORY":
            subject_words = ["история", "истории"]
        for word in subject_words:
            m = re.search(
                rf"\b{word}\b\s*[,—–:-]?\s*([^.!?\n]+)",
                raw,
                flags=re.IGNORECASE,
            )
            if m:
                candidate = re.split(
                    r"\b(?:сделай|подготовь|создай|урок|рабочий лист|провероч\w*|домашн\w*)\b",
                    m.group(1),
                    maxsplit=1,
                    flags=re.IGNORECASE,
                )[0]
                candidate = _normalize_topic(candidate)
                if candidate:
                    return candidate
        return None


@dataclass
class WorkflowExecutionWarning:
    message: str


class NaturalLanguageWorkflowService:
    def __init__(self):
        self.parser = NaturalLanguageParser()
        self.generator = PedagogyGenerationService()
        self.output = OutputService()
        self.memory = MemoryService()

    def preview(self, request: NaturalWorkflowRequest) -> WorkflowPlan:
        return self.parser.parse(request)

    async def run(
        self,
        session,
        request: NaturalWorkflowRequest,
        *,
        owner_principal: str | None = None,
    ) -> dict:
        plan = self.parser.parse(request)
        warnings = list(plan.notes)
        results = []
        course_context = None
        if request.class_course_id:
            try:
                course_context = await self.memory.build_class_course_context(
                    session, request.class_course_id
                )
            except LookupError:
                return {
                    "status": "planned", "plan": plan.model_dump(mode="json"),
                    "results": [], "warnings": warnings,
                    "summary": "Курс класса не найден. Выберите существующий курс.",
                }
            # The class/subject in the message must be consistent with the
            # explicit course ID. Never mix progress from different classes.
            normalize = lambda value: re.sub(r"[\s\-–—]", "", str(value)).casefold().replace("ё", "е")
            if ((plan.class_label and normalize(plan.class_label) != normalize(course_context.get("class_label", "")))
                or (plan.grade and plan.grade != course_context.get("grade"))
                or (plan.subject and plan.subject.casefold() != str(course_context.get("subject", "")).casefold())):
                return {
                    "status": "planned", "plan": plan.model_dump(mode="json"),
                    "results": [], "warnings": warnings,
                    "summary": "Курс не соответствует классу или предмету в запросе. Генерация остановлена.",
                }
            try:
                selected_key = select_primary_source(
                    plan.source_key,
                    course_context.get("primary_source_key"),
                    any(x.artifact_type not in {"informational", "idea_enhancement"}
                        for x in plan.artifacts),
                )
            except ValueError:
                return {
                    "status": "planned", "plan": plan.model_dump(mode="json"),
                    "results": [], "warnings": warnings,
                    "summary": (
                        "Выбранный учебник не совпадает с учебником курса. "
                        "Уточните настройки источника. Генерация остановлена."
                    ),
                }
            if selected_key and selected_key != plan.source_key:
                plan.source_key = selected_key
                plan.strict_source = True
                plan.knowledge_policy = "library_only"
                plan.web_fallback_allowed = False
                warnings.append("Источник взят из сохранённого учебника курса.")
            if not plan.subject:
                plan.subject = course_context.get("subject")
            if not plan.grade:
                plan.grade = course_context.get("grade")
            if not plan.level:
                plan.level = course_context.get("course_level")
            if not plan.class_label:
                plan.class_label = course_context.get("class_label")
        is_next_lesson = bool(re.search(r"\bследующ\w*\s+урок\w*", request.message.casefold()))
        if is_next_lesson:
            # The parser may mistake generic wording for a concrete topic.
            # Use ONLY an explicitly saved next_step, not the old topic.
            next_step = (course_context or {}).get("last_lesson") or {}
            next_step = next_step.get("next_step")
            if (not next_step or not isinstance(next_step, str)
                    or not 3 <= len(next_step.strip()) <= 140 or "\n" in next_step):
                return {
                    "status": "planned", "plan": plan.model_dump(mode="json"),
                    "results": [], "warnings": warnings,
                    "summary": (
                        "Следующая тема не подтверждена в журнале курса. "
                        "Укажите тему явно или сохраните next_step после урока."
                    ),
                }
            plan.topic = next_step.strip()
            warnings.append("Тема следующего урока взята из подтверждённого next_step.")
        # Never pass the entire class record to the LLM: free-form reflections
        # and class notes may contain identifiable student information.
        llm_course_context = None
        if course_context:
            last_lesson = course_context.get("last_lesson") or {}
            progress = course_context.get("progress") or {}
            llm_course_context = {
                "class_label": course_context.get("class_label"),
                "grade": course_context.get("grade"),
                "subject": course_context.get("subject"),
                "course_level": course_context.get("course_level"),
                "last_lesson": {
                    "date": last_lesson.get("date"),
                    "topic": last_lesson.get("topic"),
                    "status": last_lesson.get("status"),
                    "next_step": last_lesson.get("next_step"),
                },
                "progress": {
                    "unit": progress.get("unit"),
                    "topic": progress.get("topic"),
                    "subtopic": progress.get("subtopic"),
                    "status": progress.get("status"),
                },
            }

        # IDEA Enhancer and informational requests can work without curriculum topic.
        normal_artifacts = [
            x for x in plan.artifacts if x.artifact_type not in {"idea_enhancement", "informational"}
        ]
        if normal_artifacts and (not plan.subject or not plan.grade or not plan.topic):
            missing = []
            if not plan.subject:
                missing.append("предмет")
            if not plan.grade:
                missing.append("класс")
            if not plan.topic:
                missing.append("тема")
            return {
                "status": "planned",
                "plan": plan.model_dump(mode="json"),
                "results": [],
                "summary": (
                    "Запрос разобран, но для запуска генератора не хватает: "
                    + ", ".join(missing) + "."
                ),
                "warnings": warnings,
            }

        if plan.strict_source and not plan.source_key:
            return {
                "status": "planned",
                "plan": plan.model_dump(mode="json"),
                "results": [],
                "summary": ("Для строгой работы по учебнику необходимо выбрать "
                            "источник (source_key). Генерация остановлена."),
                "warnings": warnings,
            }
        if plan.strict_source and any(
            x.artifact_type in {"informational", "idea_enhancement"}
            for x in plan.artifacts
        ):
            return {
                "status": "planned",
                "plan": plan.model_dump(mode="json"),
                "results": [],
                "summary": "Строгий режим не поддерживается для данного типа ответа.",
                "warnings": warnings,
            }

        for item in plan.artifacts:
            assessment = None
            if item.artifact_type == "assessment":
                assessment = AssessmentSpec(
                    task_count=plan.assessment_task_count or 6,
                    max_points=plan.assessment_max_points or 20,
                )

            ped_request = PedagogyGenerationRequest(
                artifact_type=item.artifact_type,
                request_text=request.message,
                course_context=llm_course_context,
                subject=plan.subject,
                grade=plan.grade,
                level=plan.level,
                topic=plan.topic,
                audience=item.audience,
                duration_minutes=(
                    plan.duration_minutes
                    if item.artifact_type == "lesson"
                    else None
                ),
                mode=plan.mode,
                source_key=plan.source_key,
                strict_source=plan.strict_source,
                include_exam_perspective=True,
                knowledge_policy=plan.knowledge_policy,
                allow_web_fallback=plan.web_fallback_allowed,
                dry_run=request.dry_run,
                save_run=True,
                assessment=assessment,
                worksheet=WorksheetSpec() if item.artifact_type == "worksheet" else None,
                homework=HomeworkSpec() if item.artifact_type == "homework" else None,
            )

            item_warnings = []
            if plan.strict_source and not plan.source_key:
                item_warnings.append(
                    "Запрошен строгий режим по учебнику, но конкретный source_key "
                    "из свободного текста пока не разрешён; использован Topic Source scope."
                )

            try:
                generated = await self.generator.generate(session, ped_request)
            except PedagogyGenerationError:
                # Preserve partial workflow results rather than losing all previous artifacts.
                results.append({
                    "artifact_type": item.artifact_type,
                    "status": "failed",
                    "run_id": None,
                    "quality_score": None,
                    "files": [],
                    "warnings": item_warnings + ["Во время генерации произошла внутренняя ошибка."],
                })
                continue
            except Exception:
                logger.exception("Unexpected pedagogy generation failure")
                results.append({
                    "artifact_type": item.artifact_type,
                    "status": "failed",
                    "run_id": None,
                    "quality_score": None,
                    "files": [],
                    "warnings": item_warnings
                    + ["Во время генерации произошла внутренняя ошибка."],
                })
                continue

            files = []
            if generated.get("status") == "quality_failed":
                item_warnings.append(
                    "Материал не прошёл проверку качества и не отправлен как готовый файл."
                )
            run_id = generated.get("run_id")
            if run_id and session is not None:
                run = await session.get(GenerationRun, run_id)
                if run is not None:
                    request_json = dict(run.request_json or {})
                    if owner_principal:
                        request_json["_owner_principal"] = owner_principal
                    run.request_json = request_json
                    if course_context:
                        run.class_course_id = request.class_course_id
                        teacher_id = course_context.get("teacher_id")
                        if teacher_id:
                            run.teacher_id = uuid.UUID(teacher_id)
                    await session.commit()
            if (
                request.auto_render
                and not request.dry_run
                and plan.formats
                and run_id
                and generated.get("status") == "generated"
            ):
                audiences = []
                if item.audience in {"teacher", "both"}:
                    audiences.append("teacher")
                if item.audience in {"student", "both"}:
                    # Lesson and idea enhancer may not have a student artifact.
                    if generated.get("student_artifact") is not None:
                        audiences.append("student")

                for audience in audiences:
                    try:
                        rendered = await self.output.render(
                            session,
                            OutputRenderRequest(
                                generation_run_id=run_id,
                                audience=audience,
                                formats=plan.formats,
                                template_name=plan.template_name,
                            ),
                        )
                        for file in rendered.get("files", []):
                            files.append({
                                "export_id": str(file.get("export_id")) if file.get("export_id") else None,
                                "file_name": file["file_name"],
                                "file_format": file["file_format"],
                                "audience": file["audience"],
                                "download_path": file.get("download_path"),
                            })
                        item_warnings.extend(rendered.get("warnings", []))
                    except OutputRenderError as exc:
                        item_warnings.append(f"Export failed: {exc}")

            quality = generated.get("quality") or {}
            web_info = generated.get("web_retrieval") or {}
            item_warnings.extend(web_info.get("warnings", []))
            results.append({
                "artifact_type": item.artifact_type,
                "status": generated.get("status", "generated"),
                "run_id": str(run_id) if run_id else None,
                "quality_score": quality.get("score"),
                "files": files,
                "web_used": bool(web_info.get("performed")),
                "web_source_count": len(web_info.get("sources", []) or []),
                "web_sources": web_info.get("sources", [])[:8],
                "warnings": item_warnings,
            })

        successful = [x for x in results if x["status"] in {"generated", "dry_run"}]
        failed = [x for x in results if x["status"] in {"failed", "quality_failed"}]
        if failed and successful:
            status = "partial"
        elif failed and not successful:
            status = "failed"
        else:
            status = "planned" if request.dry_run else "completed"

        names = ", ".join(x["artifact_type"] for x in results) or "нет"
        file_count = sum(len(x["files"]) for x in results)
        summary = (
            f"Обработаны материалы: {names}. "
            f"Готовых файлов: {file_count}. "
            f"Стратегия знаний: {plan.knowledge_policy}."
        )

        return {
            "status": status,
            "plan": plan.model_dump(mode="json"),
            "results": results,
            "summary": summary,
            "warnings": warnings,
        }
