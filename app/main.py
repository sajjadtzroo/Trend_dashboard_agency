"""FastAPI entrypoint — schema bootstrap, optional seed, routers."""
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import text

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from .log import setup_logging
from .db import init_schema, SessionLocal
from .config import SEED_CSV, PG_CONNINFO, ADMIN_USERNAME, ADMIN_PASSWORD
from .importer import Importer
from .routers import dashboard, statements, management, imports, invoices
from .chat.router import router as chat_router
from .chat.graph import build_graph
from .auth.router import router as auth_router
from .auth.deps import get_current_user
from fastapi import Depends


def _seed_if_empty():
    if not Path(SEED_CSV).exists():
        logger.warning("seed file {} not found, skipping seed", SEED_CSV)
        return
    with SessionLocal() as db:
        n = db.execute(text("SELECT COUNT(*) FROM fact_transaction")).scalar_one()
        if n:
            logger.info("facts already present ({} rows), skipping seed", n)
            return
        logger.info("seeding from {}", SEED_CSV)
        result = Importer(db).run_csv(SEED_CSV)
        logger.success("seed complete: {}", result["inserted"])


def _seed_admin():
    """Create the login admin from env on first boot. No-op if it already exists."""
    from .auth.security import hash_pw
    if not ADMIN_USERNAME:
        logger.warning("ADMIN_USERNAME unset — no login accounts seeded; set ADMIN_USERNAME/ADMIN_PASSWORD")
        return
    with SessionLocal() as db:
        if db.execute(text("SELECT 1 FROM app_user WHERE username = :u"), {"u": ADMIN_USERNAME}).first():
            return
        if not ADMIN_PASSWORD:
            logger.warning("ADMIN_PASSWORD unset — admin '{}' not created", ADMIN_USERNAME)
            return
        db.execute(text("INSERT INTO app_user (username, password_hash) VALUES (:u, :h)"),
                   {"u": ADMIN_USERNAME, "h": hash_pw(ADMIN_PASSWORD)})
        db.commit()
        logger.success("seeded admin login '{}'", ADMIN_USERNAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("starting up: init schema")
    init_schema()
    if os.getenv("SEED_ON_START", "1") == "1":
        _seed_if_empty()
    _seed_admin()
    # Real checkpointer from day one (never MemorySaver): time-travel debugging of
    # bad retrievals depends on it. Same Postgres as everything else — one backup story.
    async with AsyncPostgresSaver.from_conn_string(PG_CONNINFO) as checkpointer:
        await checkpointer.setup()
        app.state.chat_graph = build_graph(checkpointer)
        logger.success("chat graph ready")
        yield
    logger.info("shutting down")


app = FastAPI(title="Creative Lab — Agency Finance API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # explicit origin (not "*") — required for allow_credentials cookies
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}


# Auth endpoints stay public; every data router requires a valid session.
app.include_router(auth_router)

_auth = [Depends(get_current_user)]
app.include_router(imports.router, dependencies=_auth)
app.include_router(dashboard.router, dependencies=_auth)
app.include_router(statements.router, dependencies=_auth)
app.include_router(management.router, dependencies=_auth)
app.include_router(invoices.router, dependencies=_auth)
app.include_router(chat_router, dependencies=_auth)
