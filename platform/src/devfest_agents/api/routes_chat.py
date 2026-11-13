from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import deps

router = APIRouter()

CONVERSATION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
MAX_MESSAGE_CHARS = 4000
KEEPALIVE_SECONDS = 15.0

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}

EXAMPLES = [
    {"label": "Finance", "prompt": "What was our operating profit by month last quarter, and which entity was most profitable?"},
    {"label": "Trading", "prompt": "What were the top 5 instruments by commission last month?"},
    {"label": "Marketing", "prompt": "How much did our ad campaigns spend last quarter, and what did each sign-up cost?"},
    {"label": "News", "prompt": "What's in the news about gold and the US dollar today?"},
    {"label": "Reconciliation (parallel)", "prompt": "Does the commission revenue we booked in Q3 match what the trading desk earned?"},
    {"label": "Budget miss (finance + trading)", "prompt": "Why did we miss revenue budget in August?"},
    {"label": "Driver + budget (sequential)", "prompt": "Which entity earned the most commission last quarter, and did it hit its revenue budget?"},
    {"label": "Driver + news (sequential)", "prompt": "Which instrument drove the most commission last month, and what's in the news about it?"},
    {"label": "Campaign worth it? (three agents)", "prompt": "Was the Nimbus Go campaign worth the money?"},
    {"label": "Segment profitability", "prompt": "Are VIP clients worth it? Compare their commission to our total operating profit."},
    {"label": "Factual (register kpi_definitions first)", "prompt": "How does Nimbus define net revenue?"},
]


class ChatRequest(BaseModel):
    conversation_id: str
    message: str


class ResetRequest(BaseModel):
    conversation_id: str


def sse_frame(event: dict) -> str:
    """One SSE frame. Keepalives are comment lines, everything else a data frame."""
    if event.get("type") == "ping":
        return ": ping\n\n"
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


async def _frames(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    async for event in events:
        yield sse_frame(event)


@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    if not CONVERSATION_ID_RE.fullmatch(body.conversation_id or ""):
        return JSONResponse({"detail": "conversation_id must be 1-128 chars of letters, digits, '-' or '_'"},
                            status_code=422)
    message = (body.message or "").strip()
    if not message:
        return JSONResponse({"detail": "message must not be empty"}, status_code=422)
    if len(message) > MAX_MESSAGE_CHARS:
        return JSONResponse({"detail": f"message is longer than {MAX_MESSAGE_CHARS} characters"}, status_code=422)
    rt = deps.runtime(request)
    events = rt.ask_stream(body.conversation_id, message, keepalive_seconds=KEEPALIVE_SECONDS)
    return StreamingResponse(_frames(events), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/api/chat/reset")
async def reset(body: ResetRequest, request: Request):
    if CONVERSATION_ID_RE.fullmatch(body.conversation_id or ""):
        await deps.runtime(request).reset(body.conversation_id)
    return {"ok": True}


@router.get("/api/chat/examples")
async def examples():
    return EXAMPLES
