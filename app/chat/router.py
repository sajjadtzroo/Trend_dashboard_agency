"""Phase 0 chat endpoint: SSE token stream from the LangGraph app.

Mirrors how the Nuxt front-end already talks to the API (see web/composables/
useApi.ts); the browser reads this as an EventSource / fetch-stream.
"""
import json
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from loguru import logger
from pydantic import BaseModel

from .guards import rate_limited

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"   # one thread_id per conversation (checkpointer key)


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    client_id = request.client.host if request.client else "anon"
    if rate_limited(client_id):
        raise HTTPException(status_code=429, detail="rate limit exceeded — slow down")

    graph = request.app.state.chat_graph
    # recursion_limit is a backstop below the in-state attempt counters (plan §6).
    config = {"configurable": {"thread_id": req.thread_id}, "recursion_limit": 15}
    inputs = {"messages": [HumanMessage(req.message)], "question_raw": req.message,
              "sql_attempts": 0}
    t0 = time.monotonic()

    async def event_stream():
        try:
            # Only the SQL answer token-streams. Doc answers are guarded before display,
            # so they're emitted whole below (never a draft shown then retracted).
            async for chunk, meta in graph.astream(inputs, config, stream_mode="messages"):
                if meta.get("langgraph_node") == "generate_sql" and getattr(chunk, "content", ""):
                    yield f"data: {json.dumps({'token': chunk.content})}\n\n"

            snap = await graph.aget_state(config)
            vals = snap.values
            if vals.get("route") == "doc":
                final = vals["messages"][-1].content   # post-guard: the answer or a refusal
                yield f"data: {json.dumps({'message': final})}\n\n"
                for i, c in enumerate(vals.get("retrieved", [])):
                    yield f"data: {json.dumps({'citation': {'n': i + 1, 'source': c.get('source_uri'), 'title': c.get('title_raw')}})}\n\n"
            elif vals.get("sql"):
                yield f"data: {json.dumps({'citation': {'sql': vals['sql']}})}\n\n"
            # Observability: one structured line per turn — route accuracy, latency, refusal.
            logger.bind(route=vals.get("route"), latency_ms=int((time.monotonic() - t0) * 1000),
                        grounded=vals.get("grounded"), retrieve_attempts=vals.get("retrieve_attempts"),
                        sql_attempts=vals.get("sql_attempts")).info("chat turn")
        except Exception:
            # A mid-stream failure (LLM down, bad key, timeout) degrades to a clean event,
            # not an unhandled TaskGroup crash that leaves the client hanging.
            logger.exception("chat turn failed")
            yield f"data: {json.dumps({'error': 'assistant is temporarily unavailable'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
