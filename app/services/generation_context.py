from __future__ import annotations

import hashlib
import json

from app.services.runtime_sop import RuntimeSOPRegistry


class GroundedContextBuilder:
    def __init__(self):
        self.sop = RuntimeSOPRegistry()

    @staticmethod
    def source_manifest(retrieval: dict | None) -> list[dict]:
        manifest = []
        seen = set()
        for hit in (retrieval or {}).get("hits", []):
            key = str(hit["chunk_id"])
            if key in seen:
                continue
            seen.add(key)
            manifest.append({
                "chunk_id": key,
                "source_id": str(hit["source_id"]),
                "source_key": hit.get("source_key"),
                "title": hit["source_title"],
                "status": hit["source_status"],
                "section": hit.get("section"),
                "page_pdf_start": hit.get("page_pdf_start"),
                "page_pdf_end": hit.get("page_pdf_end"),
                "page_print_start": hit.get("page_print_start"),
                "page_print_end": hit.get("page_print_end"),
                "quote_safe": hit.get("quote_safe", False),
                "snippet": hit.get("snippet", ""),
            })
        return manifest

    @staticmethod
    def _topic_payload(topic_card: dict | None, include_exam: bool = True) -> dict | None:
        if not topic_card:
            return None
        return {
            "subject": topic_card["subject"],
            "grade": topic_card["grade"],
            "curriculum": topic_card["curriculum"],
            "unit": topic_card["unit"],
            "topic": topic_card["topic"],
            "outcomes": sorted(topic_card.get("outcomes", []), key=lambda x: x.get("priority", 999))[:10],
            "concepts": sorted(topic_card.get("concepts", []), key=lambda x: 0 if x.get("importance") == "required" else 1)[:14],
            "skills": sorted(topic_card.get("skills", []), key=lambda x: x.get("priority", 999))[:12],
            "interdisciplinary_links": [
                x for x in topic_card.get("interdisciplinary_links", [])
                if x.get("strength") in {"strong", "useful"}
            ][:4],
            "exam_links": topic_card.get("exam_links", [])[:8] if include_exam else [],
        }

    def build(self, request, topic_card: dict | None, retrieval: dict | None, web_retrieval: dict | None = None) -> dict:
        subject_code = topic_card["subject"]["code"] if topic_card else (request.subject or "UNKNOWN")
        rules = self.sop.rules(request.artifact_type, subject_code, request.mode)
        context = {
            "artifact_type": request.artifact_type,
            "request_text": request.request_text,
            "audience": request.audience,
            "duration_minutes": request.duration_minutes,
            "mode": request.mode,
            "topic_card": self._topic_payload(topic_card, request.include_exam_perspective),
            "source_manifest": self.source_manifest(retrieval),
            "web_context": {
                "performed": bool((web_retrieval or {}).get("performed")),
                "planned": bool((web_retrieval or {}).get("planned")),
                "policy": (web_retrieval or {}).get("policy"),
                "scope": (web_retrieval or {}).get("scope"),
                "answer": (web_retrieval or {}).get("answer"),
                "sources": (web_retrieval or {}).get("sources", []),
                "citations": (web_retrieval or {}).get("citations", []),
                "allowed_domains": (web_retrieval or {}).get("allowed_domains", []),
                "search_run_id": (web_retrieval or {}).get("search_run_id"),
            },
            "runtime_sop": rules,
            "artifact_options": {
                "assessment": request.assessment.model_dump(mode="json") if getattr(request, "assessment", None) else None,
                "worksheet": request.worksheet.model_dump(mode="json") if getattr(request, "worksheet", None) else None,
                "homework": request.homework.model_dump(mode="json") if getattr(request, "homework", None) else None,
            },
            "grounding_contract": [
                "Фактическое содержание опирай на Topic Card и retrieved source snippets.",
                "Если retrieved sources пусты, не создавай точных цитат, страниц или параграфов.",
                "source_references могут содержать только entries из source_manifest.",
                "Не добавляй источник, отсутствующий в source_manifest.",
                "Версия ученика не должна раскрывать ответы/ключи в assessment и worksheet.",
                "Факты из web_context можно использовать только вместе с сохранённым списком web sources.",
                "Если web_context пуст, не утверждай, что информация была проверена в интернете.",
            ],
        }
        return context

    def build_lesson_context(self, request, topic_card: dict, retrieval: dict) -> dict:
        # Backward-compatible v0.9 pathway.
        class Adapter:
            artifact_type = "lesson"
            audience = "teacher"
            assessment = None
            worksheet = None
            homework = None
        adapter = Adapter()
        for name in [
            "request_text", "duration_minutes", "mode", "include_exam_perspective",
            "subject"
        ]:
            setattr(adapter, name, getattr(request, name, None))
        return self.build(adapter, topic_card, retrieval)

    @staticmethod
    def prompt_hash(context: dict) -> str:
        payload = json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
