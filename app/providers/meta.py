# app/providers/meta.py
# Meta Cloud API (WhatsApp Business Platform) adapter.
# Handles webhook verification, inbound message parsing, and sending replies.

import hashlib
import hmac
import json
import logging

import httpx
from fastapi import Request, Response

from app.config.settings import settings
from app.models.message import InboundMessage
from app.providers.base import ProviderAdapter
from app.providers.retry import send_with_retry

logger = logging.getLogger(__name__)

# Meta Graph API base URL
GRAPH_API_URL = "https://graph.facebook.com/v19.0"


class MetaCloudAdapter(ProviderAdapter):
    """Adapter for Meta Cloud API (official WhatsApp Business Platform)."""

    async def verify(self, request: Request) -> Response | None:
        """
        Handle the GET request Meta sends to verify the webhook.
        Meta sends: hub.mode, hub.verify_token, hub.challenge
        We must echo back hub.challenge if the token matches.
        """
        params = request.query_params

        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")

        # Only handle subscribe verification requests
        if mode == "subscribe":
            if token == settings.meta_verify_token:
                logger.info("Meta webhook verified successfully")
                return Response(content=challenge, media_type="text/plain")
            else:
                logger.warning("Meta webhook verification failed: wrong verify token")
                return Response(content="Forbidden", status_code=403)

        return None  # Not a verification request

    async def parse_inbound(self, request: Request) -> InboundMessage | None:
        """
        Parse a Meta webhook POST payload.
        Returns None for non-text messages (media, status updates, etc.)
        Raises ValueError if the signature is invalid.
        """
        body_bytes = await request.body()

        # Validate the signature if app_secret is configured
        if settings.meta_app_secret:
            self._validate_signature(body_bytes, request.headers.get("X-Hub-Signature-256", ""))

        try:
            payload = json.loads(body_bytes)
        except json.JSONDecodeError:
            logger.warning("Meta: received non-JSON payload")
            return None

        # Navigate the nested Meta payload structure
        # Structure: entry[0].changes[0].value.messages[0]
        try:
            entry = payload.get("entry", [])
            if not entry:
                return None

            changes = entry[0].get("changes", [])
            if not changes:
                return None

            value = changes[0].get("value", {})

            # Skip status updates (delivery receipts, read receipts)
            if "statuses" in value:
                logger.debug("Meta: skipping status update")
                return None

            messages = value.get("messages", [])
            if not messages:
                return None

            message = messages[0]

            # Only handle text messages
            if message.get("type") != "text":
                logger.debug(f"Meta: skipping non-text message type: {message.get('type')}")
                return None

            sender = message.get("from", "")
            text = message.get("text", {}).get("body", "")

            if not sender or not text:
                return None

            return InboundMessage(
                sender=sender,
                text=text,          # will be replaced with English translation if needed
                original_text=text,
                original_lang="en", # will be detected by translation service
                provider="meta",
                raw=payload,
            )

        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"Meta: failed to parse payload: {e}")
            return None

    async def send_message(self, to: str, text: str) -> None:
        """Send a text message via Meta Graph API with retry."""
        url = f"{GRAPH_API_URL}/{settings.meta_phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {settings.meta_access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }

        await send_with_retry(url=url, headers=headers, payload=payload, provider="meta")

    def _validate_signature(self, body: bytes, signature_header: str):
        """
        Validate the X-Hub-Signature-256 header.
        Raises ValueError if the signature doesn't match.
        """
        if not signature_header.startswith("sha256="):
            raise ValueError("Missing or malformed X-Hub-Signature-256 header")

        expected_sig = signature_header[7:]  # remove "sha256=" prefix
        computed_sig = hmac.new(
            settings.meta_app_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, computed_sig):
            logger.warning("Meta: invalid webhook signature")
            raise ValueError("Invalid webhook signature")
