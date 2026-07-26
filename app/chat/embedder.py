"""Embedder abstraction (plan §7) — one boundary so the model swaps via config + reindex.

Default: Qwen3-Embedding-8B @1024 via OpenRouter, PENDING the P0 dimensions probe.
Asymmetry (mandatory, applied identically at index and query): if OpenRouter honors
`input_type` (set EMBED_INPUT_TYPE=1 once the probe confirms it) use search_query/
search_document; otherwise fall back to a Qwen3-style query instruction prefix.
"""
import httpx

from ..config import (OPENROUTER_BASE_URL, OPENROUTER_API_KEY,
                      EMBED_MODEL, EMBED_DIMS, EMBED_INPUT_TYPE)

_QUERY_INSTRUCTION = "Instruct: Given a finance question, retrieve relevant passages\nQuery: "


def to_pgvector(vec) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in vec) + "]"


class Embedder:
    def __init__(self):
        self.model = EMBED_MODEL
        self.dims = EMBED_DIMS

    def _post(self, inputs: list[str], input_type: str | None = None) -> list[list[float]]:
        body = {"model": self.model, "input": inputs, "dimensions": self.dims}
        if EMBED_INPUT_TYPE and input_type:
            body["input_type"] = input_type
        r = httpx.post(
            f"{OPENROUTER_BASE_URL}/embeddings",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json=body, timeout=120,
        )
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._post(texts, input_type="search_document")

    def embed_query(self, text: str) -> list[float]:
        if EMBED_INPUT_TYPE:
            return self._post([text], input_type="search_query")[0]
        return self._post([_QUERY_INSTRUCTION + text])[0]  # instruction-prefix asymmetry
