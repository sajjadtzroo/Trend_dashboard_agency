"""The chat graph.

  START -> normalize -> classify -> route
    data:  plan_sql -> exec_sql (retry<=2) -> generate_sql -> END
    doc:   retrieve -> generate_doc -> guard_ground -> (END | refuse)
    refuse: refuse -> END

P2 adds the doc branch + classify router. Doc answers are NOT token-streamed: they're
guarded first, so an ungrounded draft is never shown then retracted (the endpoint emits
the final, post-guard message whole). The grade->rewrite retry loop and hybrid/rerank
retrieval are P3.
"""
import asyncio
import re
from functools import lru_cache
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from sqlalchemy import text

from ..config import LLM_MODEL, OPENROUTER_BASE_URL, OPENROUTER_API_KEY
from ..db import SessionLocal
from .normalize import normalize
from .retrieval import hybrid_search
from .prompts import (SCHEMA_CARD, ANSWER_CARD, CLASSIFY_CARD, DOC_ANSWER_CARD,
                      GRADE_CARD, REWRITE_CARD, GUARD_CARD, REFUSE_CARD, UNGROUNDED_CARD)
from .routing import route, after_plan, after_exec, after_grade, after_guard

MAX_ROWS = 100
STATEMENT_TIMEOUT = "5s"


class State(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    question_raw: str
    question_norm: str
    route: str
    # data branch
    sql: str | None
    sql_reason: str
    sql_result: list | None
    sql_error: str | None
    sql_attempts: int
    # doc branch
    retrieved: list
    retrieve_attempts: int
    sufficient: bool
    grounded: bool


class SqlPlan(BaseModel):
    sql: str | None
    reason: str


class Route(BaseModel):
    route: Literal["doc", "data", "refuse"]


class Grounded(BaseModel):
    grounded: bool


class Sufficient(BaseModel):
    sufficient: bool


class Rewrite(BaseModel):
    query: str


@lru_cache(maxsize=1)
def _get_llm() -> ChatOpenAI:
    # Lazy so an empty API key can't break app startup. temperature=1.0: Gemini 3.6
    # honors but discourages lowering it (verified 2026-07-26).
    return ChatOpenAI(
        model=LLM_MODEL, base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY, temperature=1.0, streaming=True,
    )


# --- SQL safety: defense in depth on top of the bot_ro read-only role ---
_FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|truncate|grant|revoke|create|copy)\b", re.I)


def is_safe_select(sql: str) -> bool:
    s = sql.strip().rstrip(";").strip()
    if not re.match(r"(?is)^(select|with)\b", s):
        return False
    if ";" in s:                      # single statement only
        return False
    return not _FORBIDDEN.search(s)


def _run_readonly(sql: str) -> list[dict]:
    with SessionLocal() as db:
        db.execute(text("SET LOCAL ROLE bot_ro"))
        db.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))
        res = db.execute(text(sql))
        return [dict(r) for r in res.mappings().fetchmany(MAX_ROWS)]


# --- shared ---

async def normalize_q(state: State) -> dict:
    return {"question_norm": normalize(state["question_raw"])}


async def classify(state: State) -> dict:
    r: Route = await _get_llm().with_structured_output(Route).ainvoke(
        [SystemMessage(CLASSIFY_CARD), HumanMessage(state["question_norm"])])
    return {"route": r.route}


async def refuse(state: State) -> dict:
    card = UNGROUNDED_CARD if state.get("route") == "doc" else REFUSE_CARD
    resp = await _get_llm().ainvoke([SystemMessage(card), HumanMessage(state["question_raw"])])
    return {"messages": [resp]}


# --- data branch ---

async def plan_sql(state: State) -> dict:
    plan: SqlPlan = await _get_llm().with_structured_output(SqlPlan).ainvoke([
        SystemMessage(SCHEMA_CARD),
        HumanMessage(f"Question: {state['question_norm']}\n"
                     f"Previous SQL error to fix (if any): {state.get('sql_error') or 'none'}"),
    ])
    return {"sql": plan.sql, "sql_reason": plan.reason,
            "sql_attempts": state.get("sql_attempts", 0) + 1, "sql_error": None}


async def exec_sql(state: State) -> dict:
    sql = state.get("sql") or ""
    if not is_safe_select(sql):
        return {"sql_error": "rejected: not a read-only single SELECT"}
    try:
        rows = await asyncio.to_thread(_run_readonly, sql)
        return {"sql_result": rows, "sql_error": None}
    except Exception as e:  # capture for the bounded retry loop
        return {"sql_error": str(e)[:500]}


async def generate_sql(state: State) -> dict:
    if not state.get("sql"):
        return await refuse(state)   # plan_sql declined -> out of scope
    ctx = f"SQL:\n{state['sql']}\n\nResult rows (IRR):\n{state.get('sql_result')}"
    resp = await _get_llm().ainvoke(
        [SystemMessage(ANSWER_CARD), HumanMessage(f"{state['question_raw']}\n\n{ctx}")])
    return {"messages": [resp]}


# --- doc branch ---

async def retrieve(state: State) -> dict:
    chunks = await hybrid_search(state["question_norm"])   # dense + lexical, RRF-fused
    return {"retrieved": chunks, "retrieve_attempts": state.get("retrieve_attempts", 0) + 1}


async def grade(state: State) -> dict:
    passages = "\n\n".join(c["content_raw"][:500] for c in state.get("retrieved", []))
    s: Sufficient = await _get_llm().with_structured_output(Sufficient).ainvoke(
        [SystemMessage(GRADE_CARD),
         HumanMessage(f"QUESTION: {state['question_raw']}\n\nRETRIEVED:\n{passages}")])
    return {"sufficient": s.sufficient}


async def rewrite_query(state: State) -> dict:
    r: Rewrite = await _get_llm().with_structured_output(Rewrite).ainvoke(
        [SystemMessage(REWRITE_CARD), HumanMessage(state["question_norm"])])
    return {"question_norm": normalize(r.query)}


async def generate_doc(state: State) -> dict:
    chunks = state.get("retrieved", [])
    sources = "\n\n".join(f"[{i + 1}] {c['content_raw']}" for i, c in enumerate(chunks))
    resp = await _get_llm().ainvoke(
        [SystemMessage(DOC_ANSWER_CARD), HumanMessage(f"{state['question_raw']}\n\nSOURCES:\n{sources}")])
    return {"messages": [resp]}


async def guard_ground(state: State) -> dict:
    answer = state["messages"][-1].content
    sources = "\n\n".join(c["content_raw"] for c in state.get("retrieved", []))
    g: Grounded = await _get_llm().with_structured_output(Grounded).ainvoke(
        [SystemMessage(GUARD_CARD),
         HumanMessage(f"SOURCES:\n{sources}\n\nANSWER:\n{answer}\n\nIs the answer supported?")])
    return {"grounded": g.grounded}


def build_graph(checkpointer):
    g = StateGraph(State)
    for name, fn in [("normalize", normalize_q), ("classify", classify),
                     ("plan_sql", plan_sql), ("exec_sql", exec_sql), ("generate_sql", generate_sql),
                     ("retrieve", retrieve), ("grade", grade), ("rewrite_query", rewrite_query),
                     ("generate_doc", generate_doc),
                     ("guard_ground", guard_ground), ("refuse", refuse)]:
        g.add_node(name, fn)

    g.add_edge(START, "normalize")
    g.add_edge("normalize", "classify")
    g.add_conditional_edges("classify", route,
                            {"data": "plan_sql", "doc": "retrieve", "refuse": "refuse"})
    # data branch
    g.add_conditional_edges("plan_sql", after_plan,
                            {"exec_sql": "exec_sql", "generate": "generate_sql"})
    g.add_conditional_edges("exec_sql", after_exec,
                            {"plan_sql": "plan_sql", "generate": "generate_sql"})
    g.add_edge("generate_sql", END)
    # doc branch: retrieve -> grade -> (rewrite loop | generate_doc) -> guard_ground
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", after_grade,
                            {"generate": "generate_doc", "rewrite": "rewrite_query"})
    g.add_edge("rewrite_query", "retrieve")
    g.add_edge("generate_doc", "guard_ground")
    g.add_conditional_edges("guard_ground", after_guard, {"ok": END, "refuse": "refuse"})
    g.add_edge("refuse", END)
    return g.compile(checkpointer=checkpointer)
