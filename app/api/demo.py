# app/api/demo.py
# Demo chat endpoint for local testing — no WhatsApp needed.
# POST /demo/chat  {"user_id": "test_user", "text": "What is RSI?"}
# Returns the bot's reply directly in the response.

import logging
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.models.message import InboundMessage
from app.services.message_service import MessageService

logger = logging.getLogger(__name__)

router = APIRouter()


class DemoChatRequest(BaseModel):
    user_id: str = "demo_user"   # simulates a WhatsApp sender ID
    text: str                    # the message to send to the bot


class DemoChatResponse(BaseModel):
    user_id: str
    input: str
    reply: str | None


@router.post("/demo/chat", response_model=DemoChatResponse)
async def demo_chat(body: DemoChatRequest, request: Request):
    """
    Send a message to the bot and get a reply back.
    Use this for local testing without a real WhatsApp connection.

    Example:
        curl -X POST http://localhost:8000/demo/chat \\
          -H "Content-Type: application/json" \\
          -d '{"user_id": "u1", "text": "What is RSI?"}'
    """
    message_service: MessageService = request.app.state.message_service

    # Build a fake InboundMessage
    msg = InboundMessage(
        sender=body.user_id,
        text=body.text,
        original_text=body.text,
        original_lang="en",
        provider="demo",
        raw={},
    )

    reply = await message_service.handle(msg)
    logger.info(f"[DEMO] {body.user_id}: '{body.text}' -> '{str(reply)[:80]}'")

    return DemoChatResponse(
        user_id=body.user_id,
        input=body.text,
        reply=reply,
    )
