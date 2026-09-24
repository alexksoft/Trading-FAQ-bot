# app/providers/twilio.py
# Twilio WhatsApp adapter.

import hashlib
import hmac
import logging
import urllib.parse

import httpx
from fastapi import Request, Response

from app.config.settings import settings
from app.models.message import InboundMessage
from app.providers.base import ProviderAdapter
from app.providers.retry import send_with_retry

logger = logging.getLogger(__name__)

TWILIO_API_URL = "https://api.twilio.com/2010-04-01"


class TwilioAdapter(ProviderAdapter):
    """Adapter for Twilio WhatsApp."""

    async def verify(self, request: Request) -> Response | None:
        """Twilio doesn't use a GET verification challenge — return None."""
        return None

    async def parse_inbound(self, request: Request) -> InboundMessage | None:
        """
        Parse a Twilio inbound webhook (form-encoded body).
        Validates the X-Twilio-Signature header.
        """
        body_bytes = await request.body()

        # Parse form-encoded body
        try:
            form_data = dict(urllib.parse.parse_qsl(body_bytes.decode("utf-8")))
        except Exception as e:
            logger.warning(f"Twilio: failed to parse form body: {e}")
            return None

        # Validate signature
        if settings.twilio_auth_token:
            self._validate_signature(
                request=request,
                form_data=form_data,
                signature=request.headers.get("X-Twilio-Signature", ""),
            )

        # Extract sender and message text
        sender = form_data.get("From", "").replace("whatsapp:", "")
        text = form_data.get("Body", "")

        # Skip if no text (e.g. media messages)
        if not text:
            logger.debug("Twilio: skipping non-text message")
            return None

        if not sender:
            return None

        return InboundMessage(
            sender=sender,
            text=text,
            original_text=text,
            original_lang="en",
            provider="twilio",
            raw=form_data,
        )

    async def send_message(self, to: str, text: str) -> None:
        """Send a WhatsApp message via Twilio REST API."""
        url = f"{TWILIO_API_URL}/Accounts/{settings.twilio_account_sid}/Messages.json"

        # Twilio uses HTTP Basic Auth
        auth = (settings.twilio_account_sid, settings.twilio_auth_token)
        payload = {
            "From": settings.twilio_from_number,
            "To": f"whatsapp:{to}",
            "Body": text,
        }

        await send_with_retry(url=url, auth=auth, payload=payload, provider="twilio", form=True)

    def _validate_signature(self, request: Request, form_data: dict, signature: str):
        """Validate Twilio webhook signature."""
        if not signature:
            raise ValueError("Missing X-Twilio-Signature header")

        # Build the string to sign: URL + sorted form params
        url = str(request.url)
        sorted_params = "".join(
            f"{k}{v}" for k, v in sorted(form_data.items())
        )
        string_to_sign = url + sorted_params

        computed = hmac.new(
            settings.twilio_auth_token.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()

        import base64
        computed_b64 = base64.b64encode(computed).decode("utf-8")

        if not hmac.compare_digest(computed_b64, signature):
            logger.warning("Twilio: invalid webhook signature")
            raise ValueError("Invalid Twilio webhook signature")
