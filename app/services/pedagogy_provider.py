from __future__ import annotations

from copy import deepcopy

from app.services.llm_provider import GenerationProviderError, HttpLessonProvider, TemplateLessonProvider


def source_refs(manifest: list[dict]) -> list[dict]:
    return [{
        "chunk_id": x["chunk_id"], "source_id": x["source_id"], "source_key": x.get("source_key"),
        "title": x["title"], "section": x.get("section"),
        "page_pdf_start": x.get("page_pdf_start"), "page_pdf_end": x.get("page_pdf_end"),
        "page_print_start": x.get("page_print_start"), "page_print_end": x.get("page_print_end"),
        "quote_safe": x.get("quote_safe", False),
    } for x in manifest[:5]]


class TemplatePedagogyProvider:
    name = "template"
    model = "template-pedagogy-v1"

    @staticmethod
    def _card(c): return c.get("topic_card") or {}
    @classmethod
    def _topic(cls, c): return cls._card(c).get("topic", {})
    @classmethod
    def _grade(cls, c): return cls._card(c).get("grade") or 0
    @classmethod
    def _subject(cls, c): return (cls._card(c).get("subject") or {}).get("code", "UNKNOWN")
    @classmethod
    def _concepts(cls, c):
        return [x["term"] for x in cls._card(c).get("concepts", []) if x.get("importance") == "required"][:8]
    @classmethod
    def _skills(cls, c):
        return [x.get("name") or x.get("code") for x in cls._card(c).get("skills", [])][:8]

    async def generate(self, context: dict) -> dict:
        t = context["artifact_type"]
        if t == "lesson":
            lesson = await TemplateLessonProvider().generate_lesson(context)
            lesson["artifact_type"] = "lesson"
            return {"teacher": lesson, "student": None}
        if t == "assessment": return self._assessment(context)
        if t == "worksheet": return self._worksheet(context)
        if t == "homework": return self._homework(context)
        if t == "idea_enhancement": return self._idea(context)
        raise GenerationProviderError(f"Unsupported artifact type: {t}")

    def _assessment(self, c):
        topic = self._topic(c); title = topic.get("title", "Проверочная работа")
        opts = c.get("artifact_options", {}).get("assessment") or {}
        count = int(opts.get("task_count", 6)); max_points = int(opts.get("max_points", 20))
        concepts = self._concepts(c); skills = self._skills(c)
        points = [1] * count
        for i in range(max(0, max_points - count)):
            points[count - 1 - (i % count)] += 1
        templates = [
            ("Дайте краткое определение понятия «{x}».", "Определение", "basic"),
            ("Назовите два существенных признака темы и поясните один из них.", "Признаки", "basic"),
            ("Сравните два явления темы по общему критерию.", "Сравнение", "advanced"),
            ("Рассмотрите ситуацию, определите связанное понятие и объясните ответ.", "Применение", "advanced"),
            ("Приведите конкретный пример и объясните его связь с темой.", "Пример", "advanced"),
            ("Сформулируйте причинно-следственную связь или аргументированный вывод.", "Объяснение", "high"),
        ]
        tasks = []
        for i in range(count):
            instr, skill, diff = templates[i % len(templates)]
            instr = instr.format(x=(concepts[i % len(concepts)] if concepts else title))
            tasks.append({
                "number": i + 1, "instruction": instr,
                "skill": skills[i % len(skills)] if skills else skill,
                "difficulty": diff, "points": points[i], "student_data": None,
                "answer": f"Ответ проверяется по смыслу темы «{title}».",
                "criteria": f"До {points[i]} балл(а/ов): полнота, корректность и выполнение требуемых элементов.",
            })
        teacher = {
            "artifact_type": "assessment", "title": title, "grade": self._grade(c), "subject": self._subject(c),
            "assessment_type": opts.get("assessment_type", "check"), "time_minutes": max(10, count * 4),
            "instructions": "Выполняйте задания последовательно; в объяснениях используйте предметные понятия.",
            "tasks": tasks, "max_points": sum(points),
            "grading_scale": {"5":"85–100%","4":"70–84%","3":"50–69%","2":"0–49%"} if opts.get("include_scale", True) else {},
            "common_errors_to_watch": (topic.get("typical_misconceptions") or [])[:5],
            "source_references": source_refs(c.get("source_manifest", [])),
        }
        student = deepcopy(teacher)
        for x in student["tasks"]: x["answer"] = None; x["criteria"] = None
        student["common_errors_to_watch"] = []
        return {"teacher": teacher, "student": student}

    def _worksheet(self, c):
        topic = self._topic(c); title = topic.get("title", "Рабочий лист"); concepts = self._concepts(c)
        opts = c.get("artifact_options", {}).get("worksheet") or {}
        teacher = {
            "artifact_type":"worksheet", "title":f"Рабочий лист: {title}", "grade":self._grade(c), "subject":self._subject(c),
            "purpose":"От понимания ключевого понятия к применению и собственному выводу.",
            "target_pages":int(opts.get("target_pages", 2)),
            "sections":[
                {"title":"1. Понимаю","instruction":"Отвечайте кратко и по смыслу.","tasks":[
                    {"number":1,"instruction":f"Объясните своими словами понятие «{concepts[0] if concepts else title}».","skill":"понимание","difficulty":"basic","points":0,"answer":"Передан существенный смысл понятия.","criteria":None},
                    {"number":2,"instruction":"Составьте схему ключевых признаков / причин / элементов темы.","skill":"структурирование","difficulty":"basic","points":0,"answer":"Схема отражает основные элементы темы.","criteria":None},
                ]},
                {"title":"2. Применяю","instruction":"Объясняйте ход мысли.","tasks":[
                    {"number":3,"instruction":"Разберите учебную ситуацию и объясните её связь с темой.","skill":"применение","difficulty":"advanced","points":0,"answer":"Есть корректная связь ситуации с понятием темы.","criteria":None},
                    {"number":4,"instruction":"Сформулируйте собственный пример или вывод и обоснуйте его.","skill":"объяснение","difficulty":"advanced","points":0,"answer":"Пример конкретен и объяснён.","criteria":None},
                ]},
            ],
            "support_box":["Опора: понятие → признак/причина → пример → объяснение."],
            "reflection":["Что теперь можете объяснить без подсказки?","Что осталось самым трудным?"],
            "teacher_key":["Проверять смысл, а не дословное совпадение."],
            "source_references":source_refs(c.get("source_manifest", [])),
        }
        student = deepcopy(teacher)
        for s in student["sections"]:
            for x in s["tasks"]: x["answer"] = None; x["criteria"] = None
        student["teacher_key"] = []
        return {"teacher":teacher,"student":student}

    def _homework(self, c):
        topic = self._topic(c); title = topic.get("title", "Домашнее задание"); concepts = self._concepts(c)
        opts = c.get("artifact_options", {}).get("homework") or {}
        instr = f"Повторите тему «{title}». Объясните ключевое понятие и примените его к собственному примеру."
        if concepts: instr += f" Используйте понятие «{concepts[0]}»."
        teacher = {
            "artifact_type":"homework","title":f"Домашнее задание: {title}","grade":self._grade(c),"subject":self._subject(c),
            "purpose":opts.get("purpose","consolidation"),"estimated_minutes":int(opts.get("duration_minutes",15)),
            "student_instruction":instr,
            "success_criteria":["понятие раскрыто по смыслу","пример конкретный","связь примера с темой объяснена"],
            "optional_challenge":"Сформулируйте контрпример или исключение и объясните его.",
            "teacher_note":"Проверять понимание и применение, а не объём записи.",
            "source_references":source_refs(c.get("source_manifest", [])),
        }
        student = deepcopy(teacher); student["teacher_note"] = None
        return {"teacher":teacher,"student":student}

    def _idea(self, c):
        idea = c.get("request_text", "").strip()
        teacher = {
            "artifact_type":"idea_enhancement","original_idea":idea,
            "pedagogical_value":["Авторский формат может повысить вовлечённость, если связан с измеримым результатом."],
            "weaknesses_or_risks":["Активность может стать самоцелью без предметного результата и проверки."],
            "recommended_result":"Сохранить ядро идеи и привязать его к одному измеримому результату и короткой проверке понимания.",
            "options":[
                {"label":"minimal","description":"Почти не менять идею.","implementation":["Добавить один результат","Добавить итоговый проверочный вопрос"],"risks":["Ограниченная глубина"]},
                {"label":"optimal","description":"Встроить идею в полноценную учебную логику.","implementation":["Проблемный вход","Авторская идея как центральная деятельность","Предметный вывод и проверка"],"risks":["Нужно контролировать тайминг"]},
                {"label":"bold","description":"Расширить до исследовательского/дискуссионного формата.","implementation":["Роли или позиции","Источник/данные","Аргументированный вывод"],"risks":["Больше подготовки"]},
            ],
            "recommended_option":"optimal","preserve_core":"Не заменять исходную задумку шаблонным уроком.",
            "source_references":source_refs(c.get("source_manifest", [])),
        }
        return {"teacher":teacher,"student":None}


class HttpPedagogyProvider:
    name = "http"
    def __init__(self):
        self.lesson_provider = HttpLessonProvider(); self.model = self.lesson_provider.model
    async def generate(self, context: dict) -> dict:
        if context["artifact_type"] == "lesson":
            lesson = await self.lesson_provider.generate_lesson(context); lesson["artifact_type"] = "lesson"
            return {"teacher":lesson,"student":None}
        raise GenerationProviderError("v1.0 generic HTTP adapter is implemented only for lessons; use template provider for other artifacts until a provider-specific schema adapter is configured.")
