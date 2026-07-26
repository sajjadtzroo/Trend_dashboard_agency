"""Phase 0 probe — resolves the §7 embedder fork.

Does OpenRouter's /embeddings honor the `dimensions` (MRL truncation) and
`input_type` (query/passage asymmetry) params? Their docs don't say; this
finds out empirically. If `dimensions` is honored -> Qwen3-Embedding-8B @1024
(cheaper, higher MTEB). If not -> Gemini Embedding 2 at native dims.

Run: OPENROUTER_API_KEY=sk-... python scripts/probe_embeddings.py
Optionally: EMBED_MODEL=google/gemini-embedding-2 python scripts/probe_embeddings.py
"""
import os
import sys

import httpx  # available transitively via langchain-openai -> openai

BASE = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
KEY = os.environ.get("OPENROUTER_API_KEY")
MODEL = os.getenv("EMBED_MODEL", "qwen/qwen3-embedding-8b")


def dims(**extra) -> int:
    r = httpx.post(
        f"{BASE}/embeddings",
        headers={"Authorization": f"Bearer {KEY}"},
        json={"model": MODEL, "input": "درآمد سه‌ماهه اول ۱۴۰۴", **extra},
        timeout=60,
    )
    r.raise_for_status()
    return len(r.json()["data"][0]["embedding"])


def main() -> None:
    if not KEY:
        sys.exit("set OPENROUTER_API_KEY")
    print(f"model: {MODEL}")
    native = dims()
    print(f"native dims: {native}")

    trunc = dims(dimensions=1024)
    print(f"dimensions=1024 -> {trunc} dims: "
          f"{'HONORED  ✅ (MRL works — pick Qwen3 @1024)' if trunc == 1024 else 'IGNORED ❌ (use native dims + halfvec)'}")

    try:
        dims(input_type="search_query")
        print("input_type=search_query: ACCEPTED (asymmetry via API param)")
    except httpx.HTTPStatusError as e:
        print(f"input_type: REJECTED ({e.response.status_code}) — use prompt-prefix asymmetry instead")


if __name__ == "__main__":
    main()
