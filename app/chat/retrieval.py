"""Retrieval (plan §4 doc branch).

P3: hybrid = dense (halfvec cosine) + lexical (pg_trgm word-similarity), fused with
RRF, then an optional cross-encoder rerank. Persian has no Postgres FTS dictionary,
so pg_trgm word-similarity over the NORMALIZED text is the lexical channel (§5.2).
GUCs are SET LOCAL (never session — pooler leakage) and iterative_scan is on (§8).
"""
import asyncio

from sqlalchemy import text

from ..db import SessionLocal
from ..config import EMBED_MODEL, RERANK_MODEL
from .embedder import Embedder, to_pgvector

_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


def _dense(qvec_str: str, k: int) -> list[dict]:
    with SessionLocal() as db:
        db.execute(text("SET LOCAL hnsw.ef_search = 100"))
        db.execute(text("SET LOCAL hnsw.iterative_scan = 'relaxed_order'"))
        rows = db.execute(text("""
            SELECT c.chunk_id, c.content_raw, d.title_raw, d.source_uri,
                   1 - (c.embedding <=> CAST(:q AS halfvec)) AS score
            FROM chunk c JOIN document d ON d.document_id = c.document_id
            WHERE c.embedding_model = :model
            ORDER BY c.embedding <=> CAST(:q AS halfvec)
            LIMIT :k
        """), {"q": qvec_str, "model": EMBED_MODEL, "k": k}).mappings().all()
        return [dict(r) for r in rows]


def _lexical(qnorm: str, k: int) -> list[dict]:
    # ponytail: seq scan on word_similarity. Add `WHERE :q <% c.content_norm` with a
    # tuned pg_trgm.word_similarity_threshold to use the gin_trgm index at scale.
    with SessionLocal() as db:
        rows = db.execute(text("""
            SELECT c.chunk_id, c.content_raw, d.title_raw, d.source_uri,
                   word_similarity(:q, c.content_norm) AS score
            FROM chunk c JOIN document d ON d.document_id = c.document_id
            ORDER BY word_similarity(:q, c.content_norm) DESC
            LIMIT :k
        """), {"q": qnorm, "k": k}).mappings().all()
        return [dict(r) for r in rows]


def rrf_fuse(*ranked_lists: list[dict], k: int, c: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion — rank-based, so dense/lexical scores need no calibration."""
    scores: dict[int, float] = {}
    meta: dict[int, dict] = {}
    for lst in ranked_lists:
        for rank, ch in enumerate(lst):
            cid = ch["chunk_id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (c + rank + 1)
            meta.setdefault(cid, ch)
    top = sorted(scores, key=lambda cid: -scores[cid])[:k]
    return [meta[cid] for cid in top]


def _rerank(qnorm: str, chunks: list[dict]) -> list[dict]:
    if not RERANK_MODEL:
        return chunks   # RRF order; hosted FA/EN reranker still to be confirmed (plan §7)
    # TODO: call the hosted cross-encoder once RERANK_MODEL is set and confirmed on OpenRouter.
    return chunks


async def hybrid_search(question_norm: str, k: int = 8, pool: int = 20) -> list[dict]:
    emb = get_embedder()
    qvec = await asyncio.to_thread(emb.embed_query, question_norm)
    dense = await asyncio.to_thread(_dense, to_pgvector(qvec), pool)
    lexical = await asyncio.to_thread(_lexical, question_norm, pool)
    fused = rrf_fuse(dense, lexical, k=k)
    return _rerank(question_norm, fused)


if __name__ == "__main__":
    # rrf_fuse is pure — truth-check it with no DB.
    a = [{"chunk_id": 1}, {"chunk_id": 2}, {"chunk_id": 3}]
    b = [{"chunk_id": 3}, {"chunk_id": 4}]
    out = [c["chunk_id"] for c in rrf_fuse(a, b, k=4)]
    assert out[0] == 3, out          # in both lists -> top
    assert set(out) == {1, 2, 3, 4}, out
    print("rrf_fuse OK")
