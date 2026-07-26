"""Runtime config from env (docker-compose sets these)."""
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://finance:finance@localhost:5432/finance")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))
SCHEMA_SQL = os.getenv("SCHEMA_SQL", "schema.sql")
SEED_XLSX = os.getenv("SEED_XLSX", "import_template.xlsx")
