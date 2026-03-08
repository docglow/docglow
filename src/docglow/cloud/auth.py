"""Token management for docglow Cloud authentication."""

from __future__ import annotations

import logging

from docglow.cloud.config import load_cloud_config, save_cloud_config

logger = logging.getLogger(__name__)


def store_token(token: str) -> None:
    """Store an API token for docglow Cloud."""
    save_cloud_config(token=token)
    logger.info("API token stored successfully")


def load_token() -> str | None:
    """Load the stored API token, or None if not set."""
    config = load_cloud_config()
    return config.token or None


def clear_token() -> None:
    """Remove the stored API token."""
    save_cloud_config(token="")
    logger.info("API token cleared")
