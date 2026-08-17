"""Unified secrets loader for API keys."""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SECRETS_FILE = Path(__file__).parent.parent.parent / "secrets.json"


@dataclass
class Secrets:
    """Loaded API keys."""

    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None


def load_secrets(secrets_path: Optional[Path] = None) -> Secrets:
    """Load API keys from secrets.json, falling back to environment variables.

    Priority: secrets.json > environment variables.

    Args:
        secrets_path: Path to secrets.json. Defaults to project root secrets.json.

    Returns:
        Secrets dataclass with available keys (None for missing keys).
    """
    path = secrets_path or _SECRETS_FILE
    data: dict = {}

    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            logger.debug(f"Loaded secrets from {path}")
        except Exception as e:
            logger.warning(f"Failed to read secrets.json at {path}: {e}")

    def _get(data: dict, *keys: str, env_var: str = "") -> Optional[str]:
        for k in keys:
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # Fall back to environment variable
        if env_var:
            v = os.getenv(env_var, "")
            if v.strip():
                return v.strip()
        return None

    anthropic_key = _get(
        data,
        "ANTHROPIC_API_KEY", "anthropic_api_key",
        env_var="ANTHROPIC_API_KEY",
    )
    openai_key = _get(
        data,
        "OPENAI_API_KEY", "openai_api_key",
        env_var="OPENAI_API_KEY",
    )

    if not anthropic_key:
        logger.debug("ANTHROPIC_API_KEY not found in secrets.json or environment")
    if not openai_key:
        logger.debug("OPENAI_API_KEY not found in secrets.json or environment")

    return Secrets(anthropic_api_key=anthropic_key, openai_api_key=openai_key)
