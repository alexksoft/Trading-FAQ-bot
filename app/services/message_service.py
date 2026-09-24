# app/services/message_service.py
# The main orchestrator: receives a parsed message and decides what to do with it.
# This is the heart of the bot — it calls all other services in the right order.

import logging

from app.config.config_loader import ConfigLoader
from app.models.message import InboundMessage
from app.services import matching, mentor, mentor_llm, translation, risk_calculator, analysis_engine
from app.services.session_store import get_session, save_session
from app.logging_config import log_message

logger = logging.getLogger(__name__)


class MessageService:
    """Handles one inbound message end-to-end."""

    def __init__(self, config_loader: ConfigLoader):
        self.config_loader = config_loader

    async def handle(self, msg: InboundMessage) -> str | None:
        """
        Process an inbound message and return the reply text.
        Returns None if no reply should be sent (e.g. silent mentor mode).

        Flow:
        1. Translate to English if needed
        2. Check mentor mode gate
        3. Check analysis/risk flow
        4. Check mentor commands
        5. Check analysis/risk start commands
        6. FAQ matching
        7. Fallback
        8. Translate reply back if needed
        """
        faq_config = self.config_loader.get()
        engine = matching.MatchingEngine(faq_config)

        # --- Step 1: Translate inbound message to English ---
        english_text, original_lang = await translation.to_english(msg.original_text)
        msg = msg.model_copy(update={"text": english_text, "original_lang": original_lang})

        logger.info(f"Message from {msg.sender} [{original_lang}]: '{english_text[:80]}'")

        # --- Step 2: Mentor mode gate ---
        session = get_session(msg.sender)

        # Auto-expire mentor mode if TTL has passed
        mentor.auto_expire_if_needed(session, faq_config)
        session = get_session(msg.sender)  # reload after possible expiry

        if session.mode == "human":
            # In mentor mode: pass original text, AI handles language itself
            original_msg = msg.model_copy(update={"text": msg.original_text})
            return await self._handle_mentor_mode(original_msg, session, faq_config)

        # --- Step 3: Active analysis or risk flow ---
        if session.mode == "analysis":
            reply = analysis_engine.handle_analysis_flow(msg.sender, english_text)
            log_message(msg.sender, english_text, "analysis_flow", "analysis_reply", original_lang)
            return await self._translate_reply(reply, original_lang)

        if session.mode == "risk":
            reply = risk_calculator.handle_risk_flow(msg.sender, english_text)
            log_message(msg.sender, english_text, "risk_flow", "risk_reply", original_lang)
            return await self._translate_reply(reply, original_lang)

        # --- Step 4: Mentor command (user types "mentor", "coach", etc.) ---
        if mentor.is_mentor_command(english_text):
            reply = await mentor.enter_mentor_mode(msg.sender, faq_config)
            log_message(msg.sender, english_text, "mentor_command", "mentor_entered", original_lang)
            return await self._translate_reply(reply, original_lang)

        # --- Step 5: Start analysis or risk calculator ---
        if analysis_engine.is_analysis_command(english_text):
            reply = analysis_engine.handle_analysis_flow(msg.sender, english_text)
            log_message(msg.sender, english_text, "analyze_command", "analysis_started", original_lang)
            return await self._translate_reply(reply, original_lang)

        if risk_calculator.is_risk_command(english_text):
            reply = risk_calculator.handle_risk_flow(msg.sender, english_text)
            log_message(msg.sender, english_text, "risk_command", "risk_started", original_lang)
            return await self._translate_reply(reply, original_lang)

        # --- Step 6: FAQ matching ---
        result = engine.match(english_text)

        if result.matched:
            log_message(msg.sender, english_text, result.entry_id, "faq_reply", original_lang)
            return await self._translate_reply(result.response, original_lang)

        # --- Step 7: Fallback ---
        log_message(msg.sender, english_text, "unmatched", "fallback_reply", original_lang)
        return await self._translate_reply(faq_config.fallback_message, original_lang)

    async def _handle_mentor_mode(self, msg: InboundMessage, session, faq_config) -> str | None:
        """
        Handle a message while the user is in mentor mode.
        - If they type "resume", return to bot mode
        - Otherwise, log the message and optionally reply via AI mentor
        """
        # Check for resume command
        if mentor.is_resume_command(msg.text):
            reply = mentor.resume_bot_mode(msg.sender, faq_config)
            log_message(msg.sender, msg.text, "resume_command", "bot_resumed", msg.original_lang)
            return reply

        # Log the message for the human mentor to review
        logger.info(f"[MENTOR MODE] Message from {msg.sender} logged for human review: '{msg.text[:80]}'")
        log_message(msg.sender, msg.text, "mentor_mode", "logged_for_mentor", msg.original_lang)

        # Update last_message in session
        session.last_message = msg.text
        save_session(session)

        # Try AI mentor reply if enabled
        if mentor_llm:
            # Add user message to history
            session.history.append({"role": "user", "content": msg.text})
            save_session(session)

            ai_reply = await mentor_llm.get_mentor_reply(
                history=session.history[:-1],  # history without the latest message
                user_text=msg.text,
                lang=msg.original_lang,
            )

            if ai_reply:
                # Add AI reply to history for context in next message
                session.history.append({"role": "assistant", "content": ai_reply})
                # Keep history from growing too large (last 10 exchanges)
                if len(session.history) > 20:
                    session.history = session.history[-20:]
                save_session(session)
                return ai_reply

        # AI mentor disabled or failed — stay silent (log only)
        return None

    async def _translate_reply(self, reply: str | None, target_lang: str) -> str | None:
        """Translate the reply back to the user's language if needed."""
        if reply is None:
            return None
        if target_lang == "en":
            return reply
        return await translation.from_english(reply, target_lang)
