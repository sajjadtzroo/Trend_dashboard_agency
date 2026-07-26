"""Runtime config from env (docker-compose sets these)."""
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://finance:finance@localhost:5432/finance")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))
SCHEMA_SQL = os.getenv("SCHEMA_SQL", "schema.sql")
SEED_XLSX = os.getenv("SEED_XLSX", "import_template.xlsx")

# --- RAG chatbot (Phase 0) ---
# Model from env (deprecation, preview→GA swaps). Base URL stays swappable for a future egress proxy.
LLM_MODEL = os.getenv("LLM_MODEL", "google/gemini-3.6-flash")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
# LangGraph's AsyncPostgresSaver wants a plain psycopg conninfo, not SQLAlchemy's +psycopg URL.
PG_CONNINFO = DATABASE_URL.replace("+psycopg", "")

# Embeddings (Phase 2). Default Qwen3-Embedding-8B @1024 — PENDING the P0 dimensions
# probe. If the probe says OpenRouter honors input_type, set EMBED_INPUT_TYPE=1.
# Changing EMBED_MODEL/EMBED_DIMS means ALTER the chunk.embedding column + reindex.
EMBED_MODEL = os.getenv("EMBED_MODEL", "qwen/qwen3-embedding-8b")
EMBED_DIMS = int(os.getenv("EMBED_DIMS", "1024"))
EMBED_INPUT_TYPE = os.getenv("EMBED_INPUT_TYPE", "")  # "" until the probe confirms passthrough
# Rerank (Phase 3). Empty => RRF order only, until a hosted FA/EN cross-encoder is confirmed.
RERANK_MODEL = os.getenv("RERANK_MODEL", "")
