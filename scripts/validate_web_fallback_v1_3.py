import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import types

try:
    import pgvector.sqlalchemy  # noqa: F401
except ModuleNotFoundError:
    from sqlalchemy import JSON
    pkg = types.ModuleType("pgvector")
    sub = types.ModuleType("pgvector.sqlalchemy")
    class Vector(JSON):
        pass
    sub.Vector = Vector
    pkg.sqlalchemy = sub
    sys.modules["pgvector"] = pkg
    sys.modules["pgvector.sqlalchemy"] = sub

from app.services.web_knowledge import OfficialDomainPolicy, WebFallbackPolicy

checks = {
    "ege_history_domains": OfficialDomainPolicy.allowed_domains(
        "Изменения ЕГЭ-2027 по истории", "HISTORY"
    ),
    "legal_domains": OfficialDomainPolicy.allowed_domains(
        "Действующая правовая норма и статья закона", "SOCIAL_STUDIES"
    ),
    "library_only_searches": WebFallbackPolicy.should_search(
        policy="library_only",
        local_retrieval={"hits": []},
        request_text="актуальные данные",
        allow_web_fallback=True,
        strict_source=False,
    ),
    "library_first_empty_searches": WebFallbackPolicy.should_search(
        policy="library_first",
        local_retrieval={"hits": []},
        request_text="обычный запрос",
        allow_web_fallback=True,
        strict_source=False,
    ),
}
print(json.dumps(checks, ensure_ascii=False, indent=2))
