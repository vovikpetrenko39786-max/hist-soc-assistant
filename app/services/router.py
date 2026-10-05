import re

from app.schemas.router import RoutedRequest


class RequestRouter:
    def route(self, text: str) -> RoutedRequest:
        lowered = text.lower()

        task = "unknown"
        if any(x in lowered for x in ["урок", "конспект", "провести"]):
            task = "lesson"
        elif any(x in lowered for x in ["провероч", "самостоятель", "контрольн", "тест"]):
            task = "assessment"
        elif any(x in lowered for x in ["рабочий лист", "карточ", "раздат", "материал"]):
            task = "material"
        elif any(x in lowered for x in ["дз", "домашн", "дневник.ру"]):
            task = "homework"
        elif any(x in lowered for x in ["что мы проходили", "что задавал", "на чём остановились"]):
            task = "memory_query"
        elif any(x in lowered for x in ["найди в учебнике", "на какой странице", "цитат"]):
            task = "source_query"

        subject = "unknown"
        if "обществ" in lowered:
            subject = "social_studies"
        elif "истори" in lowered:
            subject = "history"
        elif "индивидуальн" in lowered and "проект" in lowered:
            subject = "individual_project"

        grade = None
        class_label = None
        match = re.search(r"\b(5|6|7|8|9|10|11)(?:[-– ]?([а-я]))?\s*(?:класс|кл\.)?", lowered)
        if match:
            grade = int(match.group(1))
            letter = match.group(2)
            class_label = f"{grade}-{letter.upper()}" if letter else str(grade)

        mode = "default"
        if any(x in lowered for x in ["подробно", "полноцен", "полный урок"]):
            mode = "full"
        elif any(x in lowered for x in ["коротко", "только задание", "для дневника"]):
            mode = "short"
        elif any(x in lowered for x in ["через 10 минут", "через 20 минут", "ничего не готов"]):
            mode = "emergency"
        elif any(x in lowered for x in ["открытый урок", "для администрации", "аттестаци"]):
            mode = "formal"
        elif task == "lesson":
            mode = "practical"

        strict_source = any(
            x in lowered
            for x in ["по учебнику", "найди в учебнике", "точная цитата", "на какой странице"]
        )

        return RoutedRequest(
            task=task,
            subject=subject,
            grade=grade,
            class_label=class_label,
            mode=mode,
            strict_source=strict_source,
        )
