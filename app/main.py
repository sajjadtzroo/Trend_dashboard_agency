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
from .config import SEED_XLSX, PG_CONNINFO
from .importer import Importer
from .routers import dashboard, statements, management, imports, invoices
from .chat.router import router as chat_router
from .chat.graph import build_graph


def _seed_if_empty():
    if not Path(SEED_XLSX).exists():
        logger.warning("seed file {} not found, skipping seed", SEED_XLSX)
        return
    with SessionLocal() as db:
        n = db.execute(text("SELECT COUNT(*) FROM fact_transaction")).scalar_one()
        if n:
            logger.info("facts already present ({} rows), skipping seed", n)
            return
        logger.info("seeding from {}", SEED_XLSX)
        result = Importer(db).run(SEED_XLSX)
        logger.success("seed complete: {}", result["inserted"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("starting up: init schema")
    init_schema()
    if os.getenv("SEED_ON_START", "1") == "1":
        _seed_if_empty()
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
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(imports.router)
app.include_router(dashboard.router)
app.include_router(statements.router)
app.include_router(management.router)
app.include_router(invoices.router)
app.include_router(chat_router)
