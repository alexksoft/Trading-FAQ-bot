# app/services/mentor_llm.py
# AI mentor via Kiro Gateway.
# Only used when MENTOR_AI_ENABLED=true and the user is in mentor mode.
# NEVER used for normal FAQ answering.

import logging
import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Cache the mentor system prompt so we don't read the file on every message
_mentor_prompt_cache: str | None = None


def _load_mentor_prompt() -> str:
    """Load the mentor system prompt from file. Returns a default if file not found."""
    global _mentor_prompt_cache
    if _mentor_prompt_cache is not None:
        return _mentor_prompt_cache

    try:
        with open(settings.mentor_system_prompt_path, "r", encoding="utf-8") as f:
            _mentor_prompt_cache = f.read()
            logger.info(f"Mentor prompt loaded from {settings.mentor_system_prompt_path}")
            return _mentor_prompt_cache
    except FileNotFoundError:
        logger.warning(
            f"Mentor prompt file not found: {settings.mentor_system_prompt_path}. "
            f"Using default prompt."
        )
        _mentor_prompt_cache = _DEFAULT_MENTOR_PROMPT
        return _mentor_prompt_cache


async def get_mentor_reply(
    history: list[dict],
    user_text: str,
    lang: str = "en"
) -> str | None:
    """
    Call the Kiro Gateway to get an AI mentor reply.
    Returns the reply text, or None if disabled or on failure.

    history: list of {"role": "user"/"assistant", "content": "..."}
    user_text: the latest message from the learner (in English)
    lang: the learner's original language (for the prompt instruction)
    """
    # If AI mentor is disabled, return None (silent mode)
    if not settings.mentor_ai_enabled:
        logger.debug("AI mentor is disabled (MENTOR_AI_ENABLED=false)")
        return None

    if not settings.kiro_gateway_url or not settings.kiro_gateway_api_key:
        logger.warning("Kiro Gateway not configured — AI mentor unavailable")
        return None

    system_prompt = _load_mentor_prompt()

    # If the user's language is not English, ask the model to reply in their language
    if lang and lang != "en":
        system_prompt += f"\n\nIMPORTANT: The learner's language is '{lang}'. Please respond in that language."

    # Build the messages list for the API call
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)  # add conversation history
    messages.append({"role": "user", "content": user_text})

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                f"{settings.kiro_gateway_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.kiro_gateway_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-haiku-4.5",  # fast model for mentor replies
                    "messages": messages,
                    "max_tokens": 600,
                },
            )
            response.raise_for_status()
            data = response.json()
            reply = data["choices"][0]["message"]["content"]
            logger.info(f"AI mentor reply generated ({len(reply)} chars)")
            return reply

    except httpx.TimeoutException:
        logger.error("AI mentor call timed out")
        return _graceful_fallback()
    except Exception as e:
        logger.error(f"AI mentor call failed: {e}")
        return _graceful_fallback()


def _graceful_fallback() -> str:
    """Return a polite message when the AI mentor fails."""
    return (
        "I'm having trouble connecting right now. "
        "A human mentor will follow up with you shortly. "
        "Type \"resume\" anytime to return to the automatic assistant."
    )


# Default mentor system prompt used if the file is not found
_DEFAULT_MENTOR_PROMPT = """You are an educational trading mentor assistant.

Your role:
- Explain trading concepts clearly and patiently
- Help learners understand their described setups analytically
- Coach on risk management and trading process
- Ask clarifying questions to understand the learner's situation

Rules you MUST follow:
- NEVER give personalized buy/sell recommendations
- NEVER promise profits or guaranteed outcomes
- NEVER say "buy now", "sell now", or similar directive instructions
- Always frame answers as educational information
- Always remind learners that indicators need confirmation
- Always suggest they do their own research

You are a mentor, not a financial advisor. Keep responses concise and educational."""
