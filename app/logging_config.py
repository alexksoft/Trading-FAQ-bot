# app/logging_config.py
# Sets up structured logging for the whole application.
# Every processed message is logged. Unmatched messages go to unanswered.log.

import logging
import logging.handlers
import json
import os
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """
    Formats log records as JSON lines.
    This makes logs easy to parse and search.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Build a dict with the important fields
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # If extra fields were passed (like sender, match), include them
        for key in ("sender", "text", "match", "action", "lang"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(log_level: str = "INFO"):
    """
    Call this once at startup to configure all loggers.
    Creates logs/ directory if it doesn't exist.
    """
    # Make sure the logs directory exists
    os.makedirs("logs", exist_ok=True)

    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Root logger — catches everything
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove any existing handlers (avoid duplicates on reload)
    root_logger.handlers.clear()

    # --- Console handler (plain text for easy reading) ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root_logger.addHandler(console_handler)

    # --- Main app log (JSON lines, rotates daily, keeps 7 days) ---
    app_handler = logging.handlers.TimedRotatingFileHandler(
        filename="logs/app.log",
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    app_handler.setLevel(numeric_level)
    app_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(app_handler)

    # --- Unanswered queries log (separate file for easy review) ---
    # Only messages that didn't match any FAQ entry go here
    unanswered_handler = logging.handlers.TimedRotatingFileHandler(
        filename="logs/unanswered.log",
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    unanswered_handler.setLevel(logging.WARNING)
    unanswered_handler.setFormatter(JsonFormatter())

    # Create a dedicated logger for unanswered queries
    unanswered_logger = logging.getLogger("unanswered")
    unanswered_logger.addHandler(unanswered_handler)
    unanswered_logger.propagate = False  # Don't also send to root logger

    logging.info(f"Logging configured at level {log_level}")


def log_message(sender: str, text: str, match: str, action: str, lang: str = "en"):
    """
    Log a processed message to app.log.
    If unmatched, also log to unanswered.log.
    """
    logger = logging.getLogger("app.messages")

    # Use extra= to attach fields that JsonFormatter will pick up
    extra = {"sender": _mask_sender(sender), "text": text[:200], "match": match, "action": action, "lang": lang}
    logger.info("message processed", extra=extra)

    # Also write to unanswered.log if nothing matched
    if match == "unmatched":
        unanswered = logging.getLogger("unanswered")
        unanswered.warning("unmatched query", extra=extra)


def _mask_sender(sender: str) -> str:
    """
    Partially mask the sender's phone number for privacy.
    e.g. "+15551234567" -> "+1555***4567"
    """
    if len(sender) > 7:
        return sender[:5] + "***" + sender[-4:]
    return "***"
