# app/providers/retry.py
# Retry logic for sending messages.
# If the provider API fails, we retry a few times with exponential backoff.

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

# How many times to retry a failed send
MAX_RETRIES = 3
# Starting delay in seconds (doubles each retry: 1s, 2s, 4s)
BASE_DELAY = 1.0


async def send_with_retry(
    url: str,
    payload: dict,
    headers: dict = None,
    auth: tuple = None,
    provider: str = "unknown",
    form: bool = False,
) -> None:
    """
    Send an HTTP POST request with retry on failure.
    - form=True sends as form-encoded (for Twilio)
    - form=False sends as JSON (for Meta, 360dialog)
    """
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if form:
                    # Twilio uses form-encoded
                    response = await client.post(
                        url,
                        data=payload,
                        auth=auth,
                    )
                else:
                    response = await client.post(
                        url,
                        json=payload,
                        headers=headers or {},
                    )

                # Raise an exception for 4xx/5xx responses
                response.raise_for_status()
                logger.debug(f"[{provider}] Message sent successfully (attempt {attempt})")
                return  # Success!

        except httpx.HTTPStatusError as e:
            last_error = e
            logger.warning(
                f"[{provider}] Send failed (attempt {attempt}/{MAX_RETRIES}): "
                f"HTTP {e.response.status_code}"
            )
        except Exception as e:
            last_error = e
            logger.warning(
                f"[{provider}] Send failed (attempt {attempt}/{MAX_RETRIES}): {e}"
            )

        # Wait before retrying (exponential backoff)
        if attempt < MAX_RETRIES:
            delay = BASE_DELAY * (2 ** (attempt - 1))
            logger.debug(f"[{provider}] Retrying in {delay}s...")
            await asyncio.sleep(delay)

    # All retries exhausted
    logger.error(
        f"[{provider}] Failed to send message after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )
