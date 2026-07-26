"""Phase 2 ingestion: parse -> normalize -> chunk -> embed -> upsert (plan §9).

P2 slice: .txt/.md, one language. PDF/OCR and Jalali doc-date extraction land later.
Stores content_raw (original, for citations) AND content_norm (for embedding/lexical)
so displayed citations never show normalized text (plan §5.1).

Run: python -m app.chat.ingest path/to/doc.md --type report --lang en
"""
import argparse
import hashlib
from pathlib import Path

from sqlalchemy import text

from ..db import SessionLocal
from ..config import EMBED_MODEL
from .normalize import normalize
from .embedder import Embedder, to_pgvector

# ponytail: char-approx chunking (~4 chars/token). Swap to the embedder's own
# tokenizer once the model is locked by the probe (plan §5.4 — FA tokenizes very
# differently, so this is a stopgap for the English P2 slice only).
CHUNK_CHARS = 2000
OVERLAP = 150


def chunk_text(s: str) -> list[str]:
    out, i = [], 0
    step = CHUNK_CHARS - OVERLAP
    while i < len(s):
        out.append(s[i:i + CHUNK_CHARS])
        i += step
    return out


def run(path: str, doc_type: str, lang: str) -> None:
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(raw.encode()).hexdigest()
    emb = Embedder()

    with SessionLocal() as db:
        doc_id = db.execute(text("""
            INSERT INTO document (source_uri, title_raw, doc_type, lang, content_hash)
            VALUES (:u, :t, :ty, :l, :h)
            ON CONFLICT (source_uri, content_hash)
                DO UPDATE SET title_raw = EXCLUDED.title_raw
            RETURNING document_id
        """), {"u": str(p), "t": p.stem, "ty": doc_type, "l": lang, "h": content_hash}).scalar_one()

        # Incremental: re-ingest replaces this doc's chunks for this embedding model.
        db.execute(text("DELETE FROM chunk WHERE document_id = :d AND embedding_model = :m"),
                   {"d": doc_id, "m": EMBED_MODEL})

        chunks = chunk_text(raw)
        vecs = emb.embed_documents([normalize(c) for c in chunks])
        for i, (c, v) in enumerate(zip(chunks, vecs)):
            db.execute(text("""
                INSERT INTO chunk (document_id, ord, content_raw, content_norm,
                                   token_count, embedding_model, embedding)
                VALUES (:d, :o, :raw, :norm, :tc, :m, CAST(:e AS halfvec))
                ON CONFLICT (document_id, ord, embedding_model) DO NOTHING
            """), {"d": doc_id, "o": i, "raw": c, "norm": normalize(c),
                   "tc": len(c) // 4, "m": EMBED_MODEL, "e": to_pgvector(v)})
        db.commit()
    print(f"ingested {p.name}: document {doc_id}, {len(chunks)} chunks @ {EMBED_MODEL}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--type", default="report")
    ap.add_argument("--lang", default="en")
    a = ap.parse_args()
    run(a.path, a.type, a.lang)
