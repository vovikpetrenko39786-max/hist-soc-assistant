from __future__ import annotations

import hashlib
import json
from urllib.parse import urlsplit, urlunsplit

from app.services.runtime_sop import RuntimeSOPRegistry


class GroundedContextBuilder:
    def __init__(self):
        self.sop = RuntimeSOPRegistry()

    @staticmethod
    def _url_identity(url: str | None) -> str | None:
        if not url:
            return None
        parsed = urlsplit(str(url))
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return None
        return urlunsplit((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            parsed.query,
            "",
        ))

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
                "source_title": hit["source_title"],
                "url": hit.get("url"),
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
    def _normalize_web_sources(web_retrieval: dict | None) -> list[dict]:
        web_retrieval = web_retrieval or {}
        citations_by_url = {}
        for citation in web_retrieval.get("citations", []) or []:
            if not isinstance(citation, dict):
                continue
            url_identity = GroundedContextBuilder._url_identity(citation.get("url"))
            if url_identity:
                citations_by_url.setdefault(url_identity, {}).update({
                    key: value for key, value in citation.items() if value is not None
                })

        candidates = []
        for source in web_retrieval.get("sources", []) or []:
            if isinstance(source, dict):
                citation = citations_by_url.get(
                    GroundedContextBuilder._url_identity(source.get("url")),
                    {},
                )
                candidates.append({
                    **citation,
                    **{key: value for key, value in source.items() if value is not None},
                })
            else:
                candidates.append(source)
        candidate_urls = {
            GroundedContextBuilder._url_identity(item.get("url"))
            for item in candidates
            if isinstance(item, dict) and GroundedContextBuilder._url_identity(item.get("url"))
        }
        candidates.extend(
            citation for url, citation in citations_by_url.items()
            if url not in candidate_urls
        )

        normalized = []
        seen = set()
        for source in candidates:
            if not isinstance(source, dict):
                continue
            url = source.get("url")
            parsed_url = urlsplit(str(url)) if url else None
            identity_url = GroundedContextBuilder._url_identity(url)
            valid_url = identity_url is not None
            source_id = source.get("source_id")
            source_key = source.get("source_key")
            if not valid_url and not source_id and not source_key:
                continue

            title = str(source.get("title") or source.get("source_title") or url or source_id or source_key)
            start_index = source.get("start_index")
            end_index = source.get("end_index")
            identity = identity_url or str(source_id or source_key)
            chunk_id = source.get("chunk_id")
            if not chunk_id:
                digest_input = json.dumps(
                    [identity, title, start_index, end_index],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                chunk_id = f"web-{hashlib.sha256(digest_input.encode('utf-8')).hexdigest()[:24]}"
            if not source_id:
                domain = parsed_url.netloc.lower() if valid_url else str(source_key)
                source_id = f"web:{domain}"

            entry = {
                "chunk_id": str(chunk_id),
                "source_id": str(source_id),
                "title": title,
                "source_title": title,
                "status": source.get("status", source.get("source_status")),
                "origin": "web",
                "retrieval_origin": "web",
            }
            if valid_url:
                entry["url"] = str(url)
            if source_key:
                entry["source_key"] = source_key
            for field in (
                "page_pdf_start", "page_pdf_end", "page_print_start", "page_print_end",
                "start_index", "end_index",
            ):
                value = source.get(field)
                if value is not None:
                    entry[field] = value

            duplicate_key = (identity, str(chunk_id))
            if duplicate_key in seen:
                continue
            seen.add(duplicate_key)
            normalized.append(entry)
        return normalized

    @staticmethod
    def _merge_manifests(library_manifest: list[dict], web_manifest: list[dict]) -> list[dict]:
        manifest = [dict(entry) for entry in library_manifest]

        def identifiers(entry):
            keys = set()
            url = entry.get("url")
            if url:
                parsed = urlsplit(str(url))
                if parsed.scheme and parsed.netloc:
                    keys.add(("url", urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))))
            for field in ("source_id", "source_key"):
                value = entry.get(field)
                if value:
                    keys.add((field, str(value).casefold()))
            return keys

        for web_entry in web_manifest:
            web_keys = identifiers(web_entry)
            duplicate = next(
                (entry for entry in manifest if web_keys & identifiers(entry)),
                None,
            )
            if duplicate is None:
                manifest.append(dict(web_entry))
                continue
            for field, value in web_entry.items():
                if field in {"chunk_id", "source_id", "source_key", "page_pdf_start", "page_pdf_end", "page_print_start", "page_print_end"}:
                    continue
                if duplicate.get(field) is None and value is not None:
                    duplicate[field] = value
            for field in ("page_pdf_start", "page_pdf_end", "page_print_start", "page_print_end"):
                if duplicate.get(field) is None and web_entry.get(field) is not None:
                    duplicate[field] = web_entry[field]
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
            "source_manifest": self._merge_manifests(
                self.source_manifest(retrieval),
                self._normalize_web_sources(web_retrieval),
            ),
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
