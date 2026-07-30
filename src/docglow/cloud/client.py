"""HTTP client for the docglow Cloud API."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from docglow import __version__
from docglow.cloud.config import CloudConfig

logger = logging.getLogger(__name__)

# Vercel rejects function request bodies over 4.5 MB at the edge, before Cloud's
# code runs, with an opaque FUNCTION_PAYLOAD_TOO_LARGE. The legacy inline-upload
# endpoint therefore cannot carry a tarball anywhere near that size; the multipart
# envelope counts toward the body, so the practical ceiling is lower still. Used
# only to decide whether falling back to that endpoint could possibly succeed.
LEGACY_UPLOAD_LIMIT_BYTES = 4 * 1024 * 1024

# Retries for the two small JSON calls. Both are safe to repeat: minting allocates
# nothing, and finalize reports an already-finalized publish rather than
# duplicating it.
_JSON_RETRY_ATTEMPTS = 3
_JSON_RETRY_BACKOFF_SECONDS = 1.5


class CloudApiError(Exception):
    """Error from the docglow Cloud API.

    The message is printed verbatim to the user by ``docglow publish``, so it must
    always read as an instruction to a dbt engineer — never a raw JSON body from
    an upstream service.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CloudUploadUrlUnsupportedError(Exception):
    """The server has no /api/v1/publish/upload-url route (predates CLI 0.9.0).

    Internal control-flow signal, never shown to the user: ``run_publish`` catches
    it to decide between the legacy inline upload and a clear error.
    """


class CloudClient:
    """Client for interacting with the docglow Cloud API."""

    def __init__(self, config: CloudConfig) -> None:
        try:
            import httpx
        except ImportError as e:
            raise ImportError(
                "httpx is required for cloud features. Install it with: pip install docglow[cloud]"
            ) from e

        self._httpx = httpx
        self._config = config
        headers: dict[str, str] = {
            "Authorization": f"Bearer {config.token}",
            # Versioned so the server can tell which clients still use the
            # deprecated inline-upload endpoint and know when it is safe to remove.
            "User-Agent": f"docglow-cli/{__version__}",
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

    # -- Publish: signed-upload flow -------------------------------------------

    def create_upload_url(self) -> dict[str, Any]:
        """Ask Cloud for a URL to upload the artifact tarball directly to.

        Returns the ``data`` object: ``upload_url``, ``expected_version``, and
        ``max_bytes``.

        Raises:
            CloudUploadUrlUnsupportedError: the route does not exist (older server).
            CloudApiError: any other refusal, carrying the server's own message.
        """
        response = self._request_with_retry("POST", "/api/v1/publish/upload-url")

        if response.status_code == 404:
            raise CloudUploadUrlUnsupportedError()

        if response.status_code != 200:
            raise CloudApiError(
                self._explain(response, "Could not start upload"),
                status_code=response.status_code,
            )

        payload: dict[str, Any] = response.json()
        raw = payload.get("data", payload)
        data: dict[str, Any] = raw if isinstance(raw, dict) else {}
        if not data.get("upload_url"):
            raise CloudApiError("Cloud returned no upload URL. Please retry.")
        return data

    def upload_artifacts(
        self,
        upload_url: str,
        artifacts_path: Path,
        *,
        on_progress: Callable[[int], None] | None = None,
    ) -> None:
        """PUT the tarball straight to storage, bypassing the API entirely.

        Deliberately does NOT reuse ``self._client``. That client carries the
        ``Authorization: Bearer dg_live_…`` API token and, when configured, the
        ``x-vercel-protection-bypass`` shared secret — neither of which the storage
        host needs, and sending either would leak a credential into a third
        party's request logs. The signed URL's own ``?token=`` query parameter is
        the sole authorization for this request.
        """
        httpx = self._httpx
        total = artifacts_path.stat().st_size
        response = None

        # write=None: an upload is bounded by the signed URL's validity, not by a
        # per-write deadline. The API client's flat 60s timeout would abort a large
        # tarball mid-transfer on a slow uplink.
        # follow_redirects=False: never replay a body carrying ?token= to another
        # host.
        with httpx.Client(
            headers={},
            timeout=httpx.Timeout(connect=15.0, write=None, read=300.0, pool=15.0),
            follow_redirects=False,
        ) as upload_client:
            # Exactly one retry. A failed or partial PUT leaves no object, so
            # repeating it is safe — but re-minting and re-uploading in a loop is
            # not, because the version stays the same until someone finalizes.
            for attempt in range(2):
                try:
                    with artifacts_path.open("rb") as handle:
                        source: Any = (
                            _ProgressReader(handle, on_progress)
                            if on_progress is not None
                            else handle
                        )
                        response = upload_client.put(
                            upload_url,
                            content=source,
                            headers={
                                "content-type": "application/gzip",
                                "cache-control": "max-age=3600",
                            },
                        )
                    break
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt == 0:
                        logger.warning("Upload failed (%s); retrying once...", exc)
                        continue
                    raise CloudApiError(
                        f"Upload interrupted after {_mb(total)} MB "
                        f"({exc.__class__.__name__}). Check your connection and re-run "
                        "`docglow publish`."
                    ) from exc

        assert response is not None  # the loop either breaks with one or raises

        if response.status_code in (200, 201):
            return

        if response.status_code == 409:
            raise CloudApiError(
                "Another publish for this project is already uploading this version. "
                "Wait for it to finish, then re-run `docglow publish`.",
                status_code=409,
            )

        if response.status_code == 413:
            raise CloudApiError(
                f"Artifacts are {_mb(total)} MB, which exceeds the storage upload "
                "limit for your workspace. Contact support@docglow.com if you need "
                "a higher limit.",
                status_code=413,
            )

        # Never surface the storage service's own JSON body — it is meaningless to
        # a dbt engineer.
        raise CloudApiError(
            f"Upload failed (HTTP {response.status_code}). Please retry; if it "
            "persists, contact support@docglow.com.",
            status_code=response.status_code,
        )

    def finalize_publish(self, expected_version: int | None = None) -> dict[str, Any]:
        """Record the publish for an artifact already uploaded to storage.

        ``expected_version`` is a cross-check only — the server derives the real
        version itself and reports a mismatch rather than honouring ours.
        """
        body: dict[str, Any] = {}
        if expected_version is not None:
            body["expected_version"] = expected_version

        response = self._request_with_retry("POST", "/api/v1/publish/finalize", json=body)

        if response.status_code in (200, 202):
            result: dict[str, Any] = response.json()
            return result

        # A concurrent publish already recorded this version. That publish carries
        # our artifact, so treat this as success and let the caller poll the winner
        # rather than failing a publish that actually landed.
        if response.status_code == 409:
            payload = self._json_or_none(response)
            if payload and payload.get("code") == "PUBLISH_ALREADY_FINALIZED":
                data = payload.get("data") or {}
                if data.get("publish_id"):
                    logger.info(
                        "This version was already finalized by a concurrent publish; "
                        "following that one."
                    )
                    return {"data": data}

        raise CloudApiError(
            self._explain(response, "Publish failed"),
            status_code=response.status_code,
        )

    # -- Publish: legacy inline upload ----------------------------------------

    def publish(self, artifacts_path: Path) -> dict[str, Any]:
        """Upload artifacts inline as multipart/form-data (DEPRECATED).

        Only reachable against a Cloud deployment that predates the signed-upload
        routes, and only for small tarballs — the hosting platform rejects request
        bodies over ~4.5 MB before Cloud sees them.
        """
        with open(artifacts_path, "rb") as f:
            response = self._client.post(
                "/api/v1/publish",
                files={"artifacts": ("artifacts.tar.gz", f, "application/gzip")},
            )

        if response.status_code not in (200, 202):
            raise CloudApiError(
                self._explain(response, "Publish failed"),
                status_code=response.status_code,
            )

        result: dict[str, Any] = response.json()
        return result

    # -- Other endpoints ------------------------------------------------------

    def get_publish_status(self, publish_id: str) -> dict[str, Any]:
        """Check the status of a publish operation.

        Retried: polling runs for minutes after a successful upload, so a transient
        blip here must not fail a publish that already landed.
        """
        response = self._request_with_retry("GET", f"/api/v1/publish/{publish_id}/status")

        if response.status_code != 200:
            raise CloudApiError(
                self._explain(response, "Status check failed"),
                status_code=response.status_code,
            )

        result: dict[str, Any] = response.json()
        return result

    def get_workspace_info(self) -> dict[str, Any]:
        """Get workspace information and status."""
        response = self._client.get("/api/v1/workspace")

        if response.status_code != 200:
            raise CloudApiError(
                self._explain(response, "Failed to get workspace info"),
                status_code=response.status_code,
            )

        result: dict[str, Any] = response.json()
        return result

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    # -- Internals ------------------------------------------------------------

    def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> Any:
        """Issue a small JSON request, retrying transport errors and 5xx.

        Network failures are translated into CloudApiError here so they surface as
        a readable message instead of an httpx traceback.
        """
        httpx = self._httpx
        last_exc: Exception | None = None

        for attempt in range(_JSON_RETRY_ATTEMPTS):
            try:
                response = self._client.request(method, url, **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < _JSON_RETRY_ATTEMPTS - 1:
                    time.sleep(_JSON_RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                raise CloudApiError(
                    f"Could not reach docglow Cloud at {self._config.api_base_url} "
                    f"({exc.__class__.__name__}). Check your connection and re-run."
                ) from exc

            if response.status_code >= 500 and attempt < _JSON_RETRY_ATTEMPTS - 1:
                time.sleep(_JSON_RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue

            return response

        raise CloudApiError(f"Request to {url} failed: {last_exc}")  # pragma: no cover

    @staticmethod
    def _json_or_none(response: Any) -> dict[str, Any] | None:
        try:
            payload = response.json()
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _explain(self, response: Any, prefix: str) -> str:
        """Turn an error response into something a dbt engineer can act on.

        Cloud writes its ``error`` field for humans, so prefer it. Fall back to the
        raw body only when there is nothing better, and truncate it — the body may
        be an HTML error page from an edge proxy.
        """
        payload = self._json_or_none(response)
        if payload:
            message = payload.get("error")
            if isinstance(message, str) and message:
                return message

        body = (response.text or "").strip()
        if not body:
            return f"{prefix} (HTTP {response.status_code})"
        return f"{prefix} (HTTP {response.status_code}): {body[:300]}"


class _ProgressReader:
    """File wrapper that reports bytes read, for an upload progress bar.

    httpx accepts any iterable of bytes as a streaming request body, so this both
    keeps peak memory flat (no read_bytes() of the whole tarball into memory) and
    gives the caller something to advance a progress bar with.
    """

    def __init__(self, handle: Any, on_progress: Callable[[int], None]) -> None:
        self._handle = handle
        self._on_progress = on_progress

    def __iter__(self) -> Any:
        while True:
            chunk = self._handle.read(64 * 1024)
            if not chunk:
                return
            self._on_progress(len(chunk))
            yield chunk


def _mb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 * 1024):.1f}"
