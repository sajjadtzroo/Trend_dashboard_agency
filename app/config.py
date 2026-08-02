"""Runtime config from env (docker-compose sets these)."""
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://finance:finance@localhost:5432/finance")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))

# --- Auth (JWT in HttpOnly cookies, Redis allowlist) ---
# JWT_SECRET MUST be overridden in production. Dev default keeps local up-and-running.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-insecure-change-me")
ACCESS_TTL = int(os.getenv("ACCESS_TTL", "1800"))          # 30 min
REFRESH_TTL = int(os.getenv("REFRESH_TTL", "1209600"))     # 14 days
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1") == "1"     # set 0 for plain-http non-localhost dev
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")
# Set to a shared parent (e.g. ".example.com") so the session cookie spans
# app.example.com + api.example.com. Empty = host-only (correct for localhost).
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", "")
# Refresh-cookie path scope. Behind a /api reverse proxy (single-origin deploy),
# set to "/" so the browser sends it to /api/auth/refresh.
COOKIE_REFRESH_PATH = os.getenv("COOKIE_REFRESH_PATH", "/auth/refresh")
LOGIN_MAX = int(os.getenv("LOGIN_MAX", "5"))               # attempts per window, per IP and per username
LOGIN_WINDOW = int(os.getenv("LOGIN_WINDOW", "900"))       # 15 min
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")           # seeded at startup if set and absent
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SCHEMA_SQL = os.getenv("SCHEMA_SQL", "schema.sql")
SEED_CSV = os.getenv("SEED_CSV", "Creative Lab Sales Funnel - 1405 Sales Funnel.csv")

# --- RAG chatbot (Phase 0) ---
# Model from env (deprecation, preview→GA swaps). Base URL stays swappable for a future egress proxy.
LLM_MODEL = os.getenv("LLM_MODEL", "google/gemini-3.6-flash")
LLM_FALLBACK = os.getenv("LLM_FALLBACK", "google/gemini-3.5-flash")  # OpenRouter tries this if primary fails
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))  # per client IP; 0 disables
# Observability: set LANGSMITH_TRACING=true + LANGSMITH_API_KEY in env for tracing (no code needed).
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
