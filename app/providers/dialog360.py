# app/providers/dialog360.py
# 360dialog WhatsApp adapter.

import json
import logging

import httpx
from fastapi import Request, Response

from app.config.settings import settings
from app.models.message import InboundMessage
from app.providers.base import ProviderAdapter
from app.providers.retry import send_with_retry

logger = logging.getLogger(__name__)


class Dialog360Adapter(ProviderAdapter):
    """Adapter for 360dialog WhatsApp Business API."""

    async def verify(self, request: Request) -> Response | None:
        """360dialog doesn't use a GET challenge — return None."""
        return None

    async def parse_inbound(self, request: Request) -> InboundMessage | None:
        """Parse a 360dialog inbound webhook (WhatsApp Cloud-style JSON)."""
        body_bytes = await request.body()

        # Validate API key from header
        api_key = request.headers.get("D360-API-KEY", "")
        if settings.dialog360_api_key and api_key != settings.dialog360_api_key:
            logger.warning("360dialog: invalid API key in webhook header")
            raise ValueError("Invalid 360dialog API key")

        try:
            payload = json.loads(body_bytes)
        except json.JSONDecodeError:
            logger.warning("360dialog: received non-JSON payload")
            return None

        # Parse the WhatsApp Cloud-style structure
        try:
            messages = payload.get("messages", [])
            if not messages:
                return None

            message = messages[0]

            if message.get("type") != "text":
                logger.debug(f"360dialog: skipping non-text message: {message.get('type')}")
                return None

            sender = message.get("from", "")
            text = message.get("text", {}).get("body", "")

            if not sender or not text:
                return None

            return InboundMessage(
                sender=sender,
                text=text,
                original_text=text,
                original_lang="en",
                provider="dialog360",
                raw=payload,
            )

        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"360dialog: failed to parse payload: {e}")
            return None

    async def send_message(self, to: str, text: str) -> None:
        """Send a message via 360dialog API."""
        url = settings.dialog360_url
        headers = {
            "D360-API-KEY": settings.dialog360_api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "to": to,
            "type": "text",
            "text": {"body": text},
        }

        await send_with_retry(url=url, headers=headers, payload=payload, provider="dialog360")
