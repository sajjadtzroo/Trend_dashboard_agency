"""SQLAlchemy engine/session + schema bootstrap."""
import time
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger
from .config import DATABASE_URL, SCHEMA_SQL

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def _wait_for_db(attempts: int = 30, delay: float = 1.0) -> None:
    """Retry until Postgres accepts connections (standalone runs without compose healthcheck)."""
    for i in range(1, attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError:
            logger.info("waiting for database... ({}/{})", i, attempts)
            time.sleep(delay)
    raise RuntimeError(f"database not reachable after {attempts} attempts")


def init_schema() -> None:
    """Run schema.sql (idempotent DDL) once at startup.

    AUTOCOMMIT so the script's own BEGIN/COMMIT manages the transaction —
    otherwise the inner COMMIT would close a wrapping engine transaction early.
    """
    _wait_for_db()
    sql = Path(SCHEMA_SQL).read_text(encoding="utf-8")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.exec_driver_sql(sql)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
