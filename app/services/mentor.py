# app/services/mentor.py
# Handles AI tutor mode: entering and resuming.
# When a user types "mentor", "tutor", "coach" etc., they are connected to the AI tutor.
# There is no human mentor — all replies come from the AI via Kiro Gateway.

import logging
from datetime import datetime, timezone, timedelta

from app.config.settings import settings
from app.models.message import SessionState
from app.services.session_store import get_session, save_session

logger = logging.getLogger(__name__)

# Commands that trigger AI tutor mode (checked case-insensitively)
MENTOR_COMMANDS = {"mentor", "coach", "review", "support", "tutor", "teacher", "ask"}
RESUME_COMMAND = "resume"


def is_mentor_command(text: str) -> bool:
    """Return True if the text is an AI tutor command."""
    return text.strip().lower() in MENTOR_COMMANDS


def is_resume_command(text: str) -> bool:
    """Return True if the text is the resume command."""
    return text.strip().lower() == RESUME_COMMAND


async def enter_mentor_mode(sender: str, faq_config) -> str:
    """
    Switch the user to AI tutor mode:
    1. Set session mode to 'ai' with an expiry time
    2. Reset conversation history
    3. Return the confirmation message to the user
    """
    session = get_session(sender)
    session.mode = "ai"
    session.history = []

    expiry = datetime.now(timezone.utc) + timedelta(hours=settings.mentor_mode_ttl_hours)
    session.until = expiry.isoformat()

    save_session(session)
    logger.info(f"AI tutor mode entered for {sender}, expires {session.until}")

    return faq_config.mentor_confirmation


def resume_bot_mode(sender: str, faq_config) -> str:
    """Return the user from AI tutor mode back to normal FAQ bot mode."""
    session = get_session(sender)
    session.mode = "bot"
    session.until = None
    session.history = []
    save_session(session)
    logger.info(f"Bot mode resumed for {sender}")
    return faq_config.resume_confirmation


def auto_expire_if_needed(session: SessionState, faq_config) -> bool:
    """
    Check if AI tutor mode has expired and auto-return to bot mode.
    Returns True if the session was expired and reset.
    """
    from app.services.session_store import is_mentor_mode_expired
    if is_mentor_mode_expired(session):
        logger.info(f"AI tutor mode auto-expired for {session.sender}")
        session.mode = "bot"
        session.until = None
        session.history = []
        save_session(session)
        return True
    return False
