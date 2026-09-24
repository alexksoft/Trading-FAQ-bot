# app/models/message.py
# Data models for inbound messages and match results.

from pydantic import BaseModel


class InboundMessage(BaseModel):
    """A normalized inbound WhatsApp message."""

    sender: str          # WhatsApp number, e.g. "+15551234567"
    text: str            # English text used by the matching engine
    original_text: str   # The text as received (may be non-English)
    original_lang: str   # ISO language code, e.g. "en", "es", "uk"
    provider: str        # "meta" | "twilio" | "dialog360"
    raw: dict            # The full raw payload from the provider


class MatchResult(BaseModel):
    """Result of trying to match a message against the FAQ."""

    entry_id: str | None   # The matched FAQ entry id, or None
    matched: bool          # True if a match was found
    response: str | None   # The response text to send, or None


class SessionState(BaseModel):
    """Per-user session state stored in memory."""

    sender: str
    # "bot" = normal FAQ mode
    # "human" = mentor mode (FAQ paused)
    # "analysis" = setup analysis flow
    # "risk" = risk calculator flow
    mode: str = "bot"
    until: str | None = None      # ISO datetime string for mentor mode expiry
    last_message: str | None = None
    step: int = 0                 # which step in analysis/risk flow
    inputs: dict = {}             # collected inputs for analysis/risk
    history: list = []            # conversation history for AI mentor
