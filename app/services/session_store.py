# app/services/session_store.py
# In-memory storage for per-user session state.
# Stores things like: is this user in mentor mode? what analysis step are they on?

import logging
from datetime import datetime, timezone
from app.models.message import SessionState

logger = logging.getLogger(__name__)

# Simple dict: sender -> SessionState
# For a single-server deployment this is fine.
# For multi-server, swap this for Redis.
_sessions: dict[str, SessionState] = {}


def get_session(sender: str) -> SessionState:
    """Get the session for a sender, creating a new one if it doesn't exist."""
    if sender not in _sessions:
        _sessions[sender] = SessionState(sender=sender)
    return _sessions[sender]


def save_session(session: SessionState):
    """Save (update) a session."""
    _sessions[session.sender] = session


def clear_session(sender: str):
    """Remove a session entirely (reset to defaults)."""
    if sender in _sessions:
        del _sessions[sender]
        logger.debug(f"Session cleared for {sender}")


def is_mentor_mode_expired(session: SessionState) -> bool:
    """
    Check if a mentor-mode session has passed its expiry time.
    Returns True if expired (should auto-return to bot mode).
    """
    if session.mode != "human" or session.until is None:
        return False
    try:
        expiry = datetime.fromisoformat(session.until)
        now = datetime.now(timezone.utc)
        # Make expiry timezone-aware if it isn't
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return now > expiry
    except Exception:
        return False
