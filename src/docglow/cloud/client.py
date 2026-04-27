"""HTTP client for the docglow Cloud API."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from docglow.cloud.config import CloudConfig

logger = logging.getLogger(__name__)


class CloudApiError(Exception):
    """Error from the docglow Cloud API."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CloudClient:
    """Client for interacting with the docglow Cloud API."""

    def __init__(self, config: CloudConfig) -> None:
        try:
            import httpx
        except ImportError as e:
            raise ImportError(
                "httpx is required for cloud features. Install it with: pip install docglow[cloud]"
            ) from e

        self._config = config
        headers: dict[str, str] = {
            "Authorization": f"Bearer {config.token}",
            "User-Agent": "docglow-cli",
        }
        bypass = os.environ.get("DOCGLOW_VERCEL_BYPASS")
        if bypass:
            headers["x-vercel-protection-bypass"] = bypass
            headers["x-vercel-set-bypass-cookie"] = "true"
        self._client = httpx.Client(
            base_url=config.api_base_url,
            headers=headers,
            timeout=60.0,
            follow_redirects=True,
        )

    def publish(self, artifacts_path: Path) -> dict[str, Any]:
        """Upload artifacts to docglow Cloud.

        Args:
            artifacts_path: Path to the artifacts tarball.

        Returns:
            Response dict with publish_id and status_url.
        """
        with open(artifacts_path, "rb") as f:
            response = self._client.post(
                "/api/v1/publish",
                files={"artifacts": ("artifacts.tar.gz", f, "application/gzip")},
            )

        if response.status_code not in (200, 202):
            raise CloudApiError(
                f"Publish failed: {response.text}",
                status_code=response.status_code,
            )

        result: dict[str, Any] = response.json()
        return result

    def get_publish_status(self, publish_id: str) -> dict[str, Any]:
        """Check the status of a publish operation."""
        response = self._client.get(f"/api/v1/publish/{publish_id}/status")

        if response.status_code != 200:
            raise CloudApiError(
                f"Status check failed: {response.text}",
                status_code=response.status_code,
            )

        result: dict[str, Any] = response.json()
        return result

    def get_workspace_info(self) -> dict[str, Any]:
        """Get workspace information and status."""
        response = self._client.get("/api/v1/workspace")

        if response.status_code != 200:
            raise CloudApiError(
                f"Failed to get workspace info: {response.text}",
                status_code=response.status_code,
            )

        result: dict[str, Any] = response.json()
        return result

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
