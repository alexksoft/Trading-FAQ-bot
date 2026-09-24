# app/config/config_loader.py
# Loads the FAQ knowledge base from faqs.yaml.
# If the file is missing or broken, startup fails with a clear message.

import logging
import yaml
from pathlib import Path

from app.models.faq import FaqConfig, FaqEntry

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Loads and holds the FAQ configuration from a YAML file."""

    def __init__(self, config_path: str):
        self.config_path = config_path
        # This will hold the loaded config after calling load()
        self.config: FaqConfig | None = None

    def load(self) -> FaqConfig:
        """
        Read faqs.yaml and return a FaqConfig object.
        Raises a clear RuntimeError if the file is missing or malformed.
        """
        path = Path(self.config_path)

        # Check the file exists
        if not path.exists():
            raise RuntimeError(
                f"FAQ config file not found: {self.config_path}\n"
                f"Please create it or set FAQ_CONFIG_PATH in your .env file."
            )

        # Read and parse the YAML
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise RuntimeError(
                f"FAQ config file is not valid YAML: {self.config_path}\n"
                f"Error: {e}"
            )

        if not isinstance(raw, dict):
            raise RuntimeError(
                f"FAQ config file must be a YAML mapping (dict), got: {type(raw)}"
            )

        # Build the FaqConfig model — pydantic will validate all fields
        try:
            self.config = FaqConfig(**raw)
        except Exception as e:
            raise RuntimeError(
                f"FAQ config file has invalid structure: {self.config_path}\n"
                f"Error: {e}"
            )

        # Pre-normalize all triggers so matching is fast at runtime
        for entry in self.config.entries:
            entry.normalized_triggers = [_normalize(t) for t in entry.triggers]

        logger.info(
            f"FAQ config loaded: {len(self.config.entries)} entries from {self.config_path}"
        )
        return self.config

    def reload(self) -> FaqConfig:
        """Reload the config from disk (called by /reload endpoint)."""
        logger.info("Reloading FAQ config...")
        return self.load()

    def get(self) -> FaqConfig:
        """Return the currently loaded config. Raises if not loaded yet."""
        if self.config is None:
            raise RuntimeError("FAQ config has not been loaded yet. Call load() first.")
        return self.config


def _normalize(text: str) -> str:
    """
    Lowercase, strip whitespace, remove surrounding punctuation.
    This is the same normalization used in the matching engine.
    """
    import re
    text = text.lower().strip()
    # Collapse multiple spaces into one
    text = re.sub(r"\s+", " ", text)
    # Remove leading/trailing punctuation
    text = text.strip(".,!?;:'\"")
    return text
