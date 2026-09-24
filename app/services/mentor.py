# app/services/mentor.py
# Handles mentor mode: entering, resuming, notifying the human mentor.
# When a user types "mentor", FAQ replies pause and a human is notified.

import logging
import httpx
from datetime import datetime, timezone, timedelta

from app.config.settings import settings
from app.models.message import SessionState
from app.services.session_store import get_session, save_session

logger = logging.getLogger(__name__)

# Commands that trigger mentor mode (checked case-insensitively)
MENTOR_COMMANDS = {"mentor", "coach", "review", "support"}
RESUME_COMMAND = "resume"


def is_mentor_command(text: str) -> bool:
    """Return True if the text is a mentor command."""
    return text.strip().lower() in MENTOR_COMMANDS


def is_resume_command(text: str) -> bool:
    """Return True if the text is the resume command."""
    return text.strip().lower() == RESUME_COMMAND


async def enter_mentor_mode(sender: str, faq_config) -> str:
    """
    Switch the user to mentor mode:
    1. Set session mode to 'human' with an expiry time
    2. Notify the configured mentor channel
    3. Return the confirmation message to send to the user
    """
    session = get_session(sender)
    session.mode = "human"
    session.history = []  # reset AI mentor history

    # Calculate expiry time
    expiry = datetime.now(timezone.utc) + timedelta(hours=settings.mentor_mode_ttl_hours)
    session.until = expiry.isoformat()

    save_session(session)
    logger.info(f"Mentor mode entered for {sender}, expires {session.until}")

    # Notify the mentor (fire and forget — don't crash if it fails)
    await _notify_mentor(sender)

    return faq_config.mentor_confirmation


def resume_bot_mode(sender: str, faq_config) -> str:
    """
    Return the user from mentor mode back to normal bot mode.
    Returns the resume confirmation message.
    """
    session = get_session(sender)
    session.mode = "bot"
    session.until = None
    session.history = []
    save_session(session)
    logger.info(f"Bot mode resumed for {sender}")
    return faq_config.resume_confirmation


def auto_expire_if_needed(session: SessionState, faq_config) -> bool:
    """
    Check if mentor mode has expired and auto-return to bot mode.
    Returns True if the session was expired and reset.
    """
    from app.services.session_store import is_mentor_mode_expired
    if is_mentor_mode_expired(session):
        logger.info(f"Mentor mode auto-expired for {session.sender}")
        session.mode = "bot"
        session.until = None
        session.history = []
        save_session(session)
        return True
    return False


async def _notify_mentor(sender: str):
    """
    Send a notification to the configured mentor channel.
    Uses MENTOR_WEBHOOK (HTTP POST) or MENTOR_NUMBER (WhatsApp message).
    Errors are logged but do NOT crash the flow.
    """
    # Try webhook first
    if settings.mentor_webhook:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    settings.mentor_webhook,
                    json={"event": "mentor_requested", "sender": sender},
                )
            logger.info(f"Mentor webhook notified for {sender}")
        except Exception as e:
            logger.error(f"Failed to notify mentor webhook: {e}")

    # If a mentor WhatsApp number is configured, send them a message
    elif settings.mentor_number:
        # We import here to avoid circular imports
        from app.providers.factory import get_provider
        try:
            provider = get_provider()
            await provider.send_message(
                to=settings.mentor_number,
                text=f"📋 New mentor request from {sender}. Please reply to them directly."
            )
            logger.info(f"Mentor WhatsApp notified for {sender}")
        except Exception as e:
            logger.error(f"Failed to notify mentor via WhatsApp: {e}")
    else:
        logger.warning("No mentor_webhook or mentor_number configured — mentor not notified")
