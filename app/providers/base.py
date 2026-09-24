# app/providers/base.py
# The common interface all provider adapters must implement.
# This means the core logic never needs to know which provider is being used.

from abc import ABC, abstractmethod
from fastapi import Request, Response
from app.models.message import InboundMessage


class ProviderAdapter(ABC):
    """Base class for WhatsApp provider adapters."""

    @abstractmethod
    async def verify(self, request: Request) -> Response | None:
        """
        Handle webhook verification/challenge from the provider.
        Return a Response if this is a verification request, or None if not.
        """
        pass

    @abstractmethod
    async def parse_inbound(self, request: Request) -> InboundMessage | None:
        """
        Parse an inbound webhook payload into an InboundMessage.
        Return None if the payload is not a text message (e.g. media, status).
        Raise an exception if the signature/token is invalid.
        """
        pass

    @abstractmethod
    async def send_message(self, to: str, text: str) -> None:
        """
        Send a text message to a WhatsApp number.
        Should retry on failure per the retry policy.
        """
        pass
