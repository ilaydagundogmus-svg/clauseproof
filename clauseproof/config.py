"""Runtime configuration. Secrets and model names come from the environment only."""

from __future__ import annotations

import os
from dataclasses import dataclass

MIN_TEXT_CHARS = 200
MAX_FILE_BYTES = 10 * 1024 * 1024
RULES_PER_CALL = 4
MAX_RETRIES = 3
REQUEST_TIMEOUT_S = 120.0
MAX_OUTPUT_TOKENS = 4096
LOW_CONFIDENCE = 0.5
MIN_QUOTE_CHARS = 15


class ConfigError(RuntimeError):
    """Raised when required configuration is missing."""


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str


def load_settings() -> Settings:
    """Read ANTHROPIC_API_KEY and ANTHROPIC_MODEL from the environment."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    model = os.environ.get("ANTHROPIC_MODEL", "").strip()
    missing = [
        name
        for name, value in (("ANTHROPIC_API_KEY", api_key), ("ANTHROPIC_MODEL", model))
        if not value
    ]
    if missing:
        raise ConfigError(f"Missing required environment variable(s): {', '.join(missing)}")
    return Settings(api_key=api_key, model=model)
