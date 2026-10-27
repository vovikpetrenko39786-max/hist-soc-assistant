"""Bounded concept search within the topic's existing source scope."""
from app.schemas.retrieval import RetrievalRequest
from app.services.retrieval import RetrievalService


async def retrieve_topic_enrichment(session, card, topic_id, retriever=None):
    retriever = retriever or RetrievalService()
    title = card["topic"]["title"]
    terms = [x.get("term", "").strip() for x in
             (card.get("key_concepts") or card.get("concepts") or [])]
    queries = list(dict.fromkeys([title, *[x for x in terms if x]]))[:4]
    hits, warnings, seen = [], [], set()
    for query in queries:
        result = await retriever.retrieve(session, RetrievalRequest(
            query=query, mode="hybrid", subject=card["subject"]["code"],
            grade=card.get("grade"),
            level=(card.get("curriculum") or {}).get("level") or card.get("level"),
            topic_id=topic_id, top_k=8, candidate_k=40, snippet_chars=2400,
        ))
        warnings.extend(result.get("warnings", []))
        for hit in result.get("hits", []):
            key = str(hit["chunk_id"])
            if key not in seen:
                seen.add(key)
                hits.append(hit)
    return {"query": title, "mode": "hybrid", "strict_source": False,
            "hits": hits, "warnings": list(dict.fromkeys(warnings))}
