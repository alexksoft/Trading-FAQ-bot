# app/models/faq.py
# Data models for the FAQ knowledge base.
# Pydantic v2 validates all fields automatically.

from typing import Literal
from pydantic import BaseModel, Field


class FaqEntry(BaseModel):
    """One FAQ entry: triggers + response."""

    id: str                                         # unique slug, e.g. "what-is-rsi"
    triggers: list[str]                             # keywords/phrases to match
    match_type: Literal["exact", "contains"] = "contains"
    priority: int = 0                               # higher = wins on tie
    response: str                                   # the answer to send back
    category: str = ""                              # informational grouping

    # This field is filled at load time with pre-normalized triggers
    # (not in the YAML, so we exclude it from serialization)
    normalized_triggers: list[str] = Field(default_factory=list, exclude=True)

    class Config:
        # Allow extra fields in YAML (like 'category') without errors
        extra = "ignore"


class FaqConfig(BaseModel):
    """The full FAQ knowledge base loaded from faqs.yaml."""

    fallback_message: str                           # reply when nothing matches
    mentor_commands: list[str] = ["mentor", "coach", "review", "support"]
    resume_command: str = "resume"
    mentor_confirmation: str = "A mentor will reply within 24 hours."
    resume_confirmation: str = "You're back with the automatic assistant."
    entries: list[FaqEntry] = []

    class Config:
        extra = "ignore"
