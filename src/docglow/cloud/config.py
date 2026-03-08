"""Cloud configuration management."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".docglow"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_API_URL = "https://api.docglow.dev"


@dataclass(frozen=True)
class CloudConfig:
    api_base_url: str = DEFAULT_API_URL
    token: str = ""
    workspace_slug: str = ""
    project_slug: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.workspace_slug)


def load_cloud_config() -> CloudConfig:
    """Load cloud configuration from file and environment variables.

    Resolution order (later overrides earlier):
    1. ~/.docglow/config.json
    2. Environment variables (DOCGLOW_TOKEN, DOCGLOW_API_URL)
    """
    file_config = _load_config_file()

    token = os.environ.get("DOCGLOW_TOKEN", file_config.get("token", ""))
    api_url = os.environ.get("DOCGLOW_API_URL", file_config.get("api_base_url", DEFAULT_API_URL))
    workspace = file_config.get("workspace_slug", "")
    project = file_config.get("project_slug", "")

    return CloudConfig(
        api_base_url=api_url,
        token=token,
        workspace_slug=workspace,
        project_slug=project,
    )


def save_cloud_config(
    *,
    token: str | None = None,
    workspace_slug: str | None = None,
    project_slug: str | None = None,
    api_base_url: str | None = None,
) -> None:
    """Save cloud configuration to ~/.docglow/config.json.

    Only updates fields that are provided (not None).
    """
    existing = _load_config_file()

    if token is not None:
        existing["token"] = token
    if workspace_slug is not None:
        existing["workspace_slug"] = workspace_slug
    if project_slug is not None:
        existing["project_slug"] = project_slug
    if api_base_url is not None:
        existing["api_base_url"] = api_base_url

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    logger.info("Cloud config saved to %s", CONFIG_FILE)


def _load_config_file() -> dict[str, str]:
    """Load the config file, returning an empty dict if not found."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to read cloud config from %s", CONFIG_FILE)
        return {}
