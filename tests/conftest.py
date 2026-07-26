"""Shared fixtures.

Endpoint tests run against the REAL running Postgres + Redis (docker compose up),
using a minimal FastAPI app that mounts the data routers WITHOUT the chat lifespan —
so no OpenRouter/langgraph is needed to exercise every non-chat endpoint.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import SessionLocal
from app.routers import dashboard, statements, management, invoices, imports


def _services_up() -> bool:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


SERVICES_UP = _services_up()
requires_services = pytest.mark.skipif(not SERVICES_UP, reason="Postgres/Redis not reachable")


@pytest.fixture(scope="session")
def app() -> FastAPI:
    a = FastAPI()

    @a.get("/health")
    def health():
        return {"status": "ok"}

    for r in (imports.router, dashboard.router, statements.router,
              management.router, invoices.router):
        a.include_router(r)
    return a


@pytest.fixture(scope="session")
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()
