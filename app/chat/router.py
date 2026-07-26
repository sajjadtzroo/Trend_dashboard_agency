"""Phase 0 chat endpoint: SSE token stream from the LangGraph app.

Mirrors how the Nuxt front-end already talks to the API (see web/composables/
useApi.ts); the browser reads this as an EventSource / fetch-stream.
"""
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"   # one thread_id per conversation (checkpointer key)


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    graph = request.app.state.chat_graph
    # recursion_limit is a backstop below the in-state attempt counters (plan §6).
    config = {"configurable": {"thread_id": req.thread_id}, "recursion_limit": 15}
    inputs = {"messages": [HumanMessage(req.message)], "question_raw": req.message,
              "sql_attempts": 0}

    async def event_stream():
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
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
