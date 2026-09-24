# app/providers/factory.py
# Returns the correct provider adapter based on the PROVIDER setting.

import logging
from app.config.settings import settings
from app.providers.base import ProviderAdapter

logger = logging.getLogger(__name__)

# Cache the provider instance so we don't create a new one on every request
_provider_instance: ProviderAdapter | None = None


def get_provider() -> ProviderAdapter:
    """Return the configured provider adapter (cached singleton)."""
    global _provider_instance

    if _provider_instance is not None:
        return _provider_instance

    provider_name = settings.provider.lower()
    logger.info(f"Initializing provider: {provider_name}")

    if provider_name == "meta":
        from app.providers.meta import MetaCloudAdapter
        _provider_instance = MetaCloudAdapter()

    elif provider_name == "twilio":
        from app.providers.twilio import TwilioAdapter
        _provider_instance = TwilioAdapter()

    elif provider_name == "dialog360":
        from app.providers.dialog360 import Dialog360Adapter
        _provider_instance = Dialog360Adapter()

    else:
        raise ValueError(
            f"Unknown provider: '{provider_name}'. "
            f"Set PROVIDER to one of: meta, twilio, dialog360"
        )

    return _provider_instance
