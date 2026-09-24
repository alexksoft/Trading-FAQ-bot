# app/services/translation.py
# Translates non-English messages to English (for matching) and back.
# Uses Kiro Gateway LLM ONLY for translation — never for answering.
# English messages bypass this entirely (no LLM call).

import logging
import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Try to import langdetect for language detection
# If not installed, we fall back to assuming English
try:
    from langdetect import detect, LangDetectException
    _LANGDETECT_AVAILABLE = True
except ImportError:
    _LANGDETECT_AVAILABLE = False
    logger.warning("langdetect not installed — all messages treated as English")


def detect_language(text: str) -> str:
    """
    Detect the language of the text.
    Returns an ISO 639-1 code like "en", "es", "uk", "ru".
    Returns "en" if detection fails or langdetect is not available.
    """
    if not _LANGDETECT_AVAILABLE:
        return "en"

    # Short texts are hard to detect reliably — treat as English
    if len(text.strip()) < 10:
        return "en"

    try:
        lang = detect(text)
        logger.debug(f"Detected language: {lang}")
        return lang
    except Exception as e:
        logger.debug(f"Language detection failed: {e} — assuming English")
        return "en"


async def to_english(text: str) -> tuple[str, str]:
    """
    Translate text to English if it's not already English.
    Returns (english_text, original_lang).
    If translation fails, returns the original text with the detected lang.
    """
    lang = detect_language(text)

    # English — no LLM call needed
    if lang == "en":
        return text, "en"

    logger.info(f"Translating from {lang} to English: '{text[:50]}...'")

    translated = await _call_kiro_translate(text, target_lang="English", source_lang=lang)
    if translated:
        return translated, lang
    else:
        # Translation failed — use original text (best-effort matching)
        logger.warning(f"Translation failed, using original text for matching")
        return text, lang


async def from_english(text: str, target_lang: str) -> str:
    """
    Translate an English response back to the user's language.
    If translation fails, returns the English text (best-effort).
    """
    if target_lang == "en":
        return text

    logger.info(f"Translating response to {target_lang}")

    translated = await _call_kiro_translate(text, target_lang=target_lang, source_lang="en")
    if translated:
        return translated
    else:
        logger.warning(f"Outbound translation failed, replying in English")
        return text


async def _call_kiro_translate(text: str, target_lang: str, source_lang: str) -> str | None:
    """
    Call the Kiro Gateway to translate text.
    Returns the translated text, or None on failure.
    """
    if not settings.kiro_gateway_url or not settings.kiro_gateway_api_key:
        logger.warning("Kiro Gateway not configured — translation unavailable")
        return None

    prompt = (
        f"Translate the following text from {source_lang} to {target_lang}. "
        f"Return ONLY the translated text, nothing else.\n\n"
        f"Text to translate:\n{text}"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{settings.kiro_gateway_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.kiro_gateway_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-haiku-4.5",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                },
            )
            response.raise_for_status()
            data = response.json()
            translated = data["choices"][0]["message"]["content"].strip()
            return translated

    except httpx.TimeoutException:
        logger.error("Translation call timed out")
        return None
    except Exception as e:
        logger.error(f"Translation call failed: {e}")
        return None
