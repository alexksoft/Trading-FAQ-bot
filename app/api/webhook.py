# app/api/webhook.py
# The webhook endpoint that receives messages from WhatsApp providers.
# Also exposes /health and /reload endpoints.

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.providers.factory import get_provider
from app.services.message_service import MessageService

logger = logging.getLogger(__name__)

# Track when the app started (for uptime reporting)
_start_time = time.time()

# The router is registered in main.py
router = APIRouter()

# MessageService is injected via dependency
def get_message_service(request: Request) -> MessageService:
    """Get the MessageService from app state (set in main.py startup)."""
    return request.app.state.message_service


@router.get("/webhook/{provider}")
async def webhook_verify(provider: str, request: Request):
    """
    Handle webhook verification/challenge from the provider.
    Meta Cloud API sends a GET request to verify the webhook URL.
    """
    adapter = get_provider()
    response = await adapter.verify(request)

    if response is not None:
        return response

    # Not a verification request — return 200
    return Response(content="OK", status_code=200)


@router.post("/webhook/{provider}")
async def webhook_inbound(
    provider: str,
    request: Request,
    message_service: MessageService = Depends(get_message_service),
):
    """
    Receive an inbound message from the WhatsApp provider.
    Always returns 200 to prevent the provider from retrying.
    """
    adapter = get_provider()

    try:
        # Parse the inbound message
        msg = await adapter.parse_inbound(request)

        # If None, it's a non-text message or status update — acknowledge and skip
        if msg is None:
            logger.debug(f"[{provider}] Skipping non-text or status payload")
            return Response(content="OK", status_code=200)

        # Process the message and get a reply
        reply = await message_service.handle(msg)

        # Send the reply if we have one
        if reply:
            await adapter.send_message(to=msg.sender, text=reply)

    except ValueError as e:
        # Signature/token validation failed
        logger.warning(f"[{provider}] Webhook validation failed: {e}")
        return Response(content="Forbidden", status_code=403)

    except Exception as e:
        # Unexpected error — log it but still return 200 to avoid redelivery storms
        logger.error(f"[{provider}] Unexpected error handling webhook: {e}", exc_info=True)

    # Always return 200 to the provider
    return Response(content="OK", status_code=200)


@router.get("/health")
async def health_check(request: Request):
    """
    Health check endpoint.
    Returns service status, provider, FAQ count, and uptime.
    """
    uptime_seconds = int(time.time() - _start_time)
    faq_count = 0

    try:
        config = request.app.state.config_loader.get()
        faq_count = len(config.entries)
    except Exception:
        pass

    return JSONResponse({
        "status": "healthy",
        "provider": settings.provider,
        "faq_count": faq_count,
        "uptime_seconds": uptime_seconds,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@router.post("/reload")
async def reload_config(request: Request):
    """
    Reload the FAQ config from disk without restarting.
    Protected by ADMIN_TOKEN.
    """
    # Check admin token
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not settings.admin_token or token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")

    try:
        config = request.app.state.config_loader.reload()
        # Rebuild the matching engine with the new config
        from app.services.matching import MatchingEngine
        request.app.state.message_service = MessageService(request.app.state.config_loader)
        logger.info(f"Config reloaded: {len(config.entries)} entries")
        return JSONResponse({"status": "reloaded", "faq_count": len(config.entries)})
    except Exception as e:
        logger.error(f"Config reload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
