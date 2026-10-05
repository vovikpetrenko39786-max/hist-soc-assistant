import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
import json


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


from app.services.embeddings import HashEmbeddingProvider


async def main():
    provider = HashEmbeddingProvider(dim=384)
    q = await provider.embed_query("признаки социального института")
    d1 = (await provider.embed_documents(["социальный институт признаки функции"]))[0]
    d2 = (await provider.embed_documents(["Карибский кризис холодная война"]))[0]

    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    result = {
        "query_dim": len(q),
        "same_topic_similarity": round(dot(q, d1), 6),
        "different_topic_similarity": round(dot(q, d2), 6),
        "same_topic_ranked_higher": dot(q, d1) > dot(q, d2),
        "provider_note": "development-only lexical hash vectors; not semantic production embeddings",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
