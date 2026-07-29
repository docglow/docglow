"""Tests for the docglow Cloud HTTP client and the three-step publish flow.

Uses httpx.MockTransport rather than respx to avoid adding a dependency to a
published CLI. Each test plants a handler that records the requests it saw, so
assertions can be made about headers and bodies — which matters here: the
direct-to-storage PUT must NOT carry our API token.
"""

from __future__ import annotations

import json
import tarfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from docglow import __version__
from docglow.cloud.client import (
    LEGACY_UPLOAD_LIMIT_BYTES,
    CloudApiError,
    CloudClient,
    CloudUploadUrlUnsupportedError,
)
from docglow.cloud.config import CloudConfig
from docglow.cloud.publish import _upload_and_finalize

API_BASE = "https://app.docglow.com"
UPLOAD_URL = (
    "https://proj.supabase.co/storage/v1/object/upload/sign/artifacts/"
    "ws-1/proj-1/v4/artifacts.tar.gz?token=signed-jwt"
)


@pytest.fixture
def config() -> CloudConfig:
    return CloudConfig(
        api_base_url=API_BASE,
        token="dg_live_secret_token",
        workspace_slug="acme",
        project_slug="analytics",
    )


@pytest.fixture
def tarball(tmp_path: Path) -> Path:
    """A real (tiny) gzipped tarball on disk."""
    payload = tmp_path / "manifest.json"
    payload.write_text(json.dumps({"nodes": {}}))
    path = tmp_path / "artifacts.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        tar.add(payload, arcname="manifest.json")
    return path


def _client_with(
    config: CloudConfig,
    handler: Callable[[httpx.Request], httpx.Response],
    recorder: list[httpx.Request] | None = None,
) -> CloudClient:
    """Build a CloudClient whose API transport (and any upload client) is mocked.

    Patching `_httpx` with a shim means `upload_artifacts`, which deliberately
    constructs its own bare client, also routes through the mock — and we can still
    inspect exactly what it sent.
    """
    client = CloudClient(config)

    def record(request: httpx.Request) -> httpx.Response:
        if recorder is not None:
            recorder.append(request)
        return handler(request)

    transport = httpx.MockTransport(record)
    client._client = httpx.Client(
        base_url=config.api_base_url,
        headers=client._client.headers,
        transport=transport,
    )

    class _HttpxShim:
        """Stands in for the httpx module so bare clients get the mock transport."""

        Timeout = httpx.Timeout
        TimeoutException = httpx.TimeoutException
        TransportError = httpx.TransportError

        # Named to match httpx.Client, which is what the code under test calls.
        @staticmethod
        def Client(**kwargs: Any) -> httpx.Client:  # noqa: N802
            kwargs.pop("follow_redirects", None)
            return httpx.Client(transport=transport, **kwargs)

    client._httpx = _HttpxShim()  # type: ignore[assignment]
    return client


# -- The security-critical assertion ------------------------------------------


def test_upload_put_carries_no_credentials(config: CloudConfig, tarball: Path) -> None:
    """The storage PUT must not leak our API token or the Vercel bypass secret.

    Signed-URL uploads are authorized solely by the ?token= query parameter. Sending
    `Authorization: Bearer dg_live_…` would put a live API token into a third
    party's request logs; sending x-vercel-protection-bypass would leak a shared
    deployment secret.
    """
    seen: list[httpx.Request] = []
    client = _client_with(config, lambda request: httpx.Response(200, json={}), recorder=seen)

    client.upload_artifacts(UPLOAD_URL, tarball)

    put = next(r for r in seen if r.method == "PUT")
    assert "authorization" not in {k.lower() for k in put.headers.keys()}
    assert "x-vercel-protection-bypass" not in {k.lower() for k in put.headers.keys()}
    assert "dg_live_secret_token" not in str(put.headers)
    assert put.headers["content-type"] == "application/gzip"
    # And it really is going to storage, not back through our API.
    assert put.url.host == "proj.supabase.co"


def test_api_requests_do_carry_the_token(config: CloudConfig) -> None:
    seen: list[httpx.Request] = []
    client = _client_with(
        config,
        lambda request: httpx.Response(
            200, json={"data": {"upload_url": UPLOAD_URL, "expected_version": 4}}
        ),
        recorder=seen,
    )

    client.create_upload_url()

    assert seen[0].headers["authorization"] == "Bearer dg_live_secret_token"
    # Versioned UA is how the server counts clients still on the legacy endpoint.
    assert seen[0].headers["user-agent"] == f"docglow-cli/{__version__}"


# -- create_upload_url --------------------------------------------------------


def test_create_upload_url_returns_the_data_object(config: CloudConfig) -> None:
    client = _client_with(
        config,
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "upload_url": UPLOAD_URL,
                    "expected_version": 4,
                    "max_bytes": 52428800,
                }
            },
        ),
    )

    assert client.create_upload_url() == {
        "upload_url": UPLOAD_URL,
        "expected_version": 4,
        "max_bytes": 52428800,
    }


def test_create_upload_url_signals_unsupported_on_404(config: CloudConfig) -> None:
    client = _client_with(config, lambda request: httpx.Response(404, text="Not Found"))

    with pytest.raises(CloudUploadUrlUnsupportedError):
        client.create_upload_url()


def test_create_upload_url_surfaces_the_servers_human_message(
    config: CloudConfig,
) -> None:
    client = _client_with(
        config,
        lambda request: httpx.Response(
            402,
            json={
                "code": "PLAN_EXPIRED",
                "error": (
                    "Your Docglow Pro subscription has expired. Upgrade to continue publishing."
                ),
            },
        ),
    )

    with pytest.raises(CloudApiError, match="subscription has expired"):
        client.create_upload_url()


# -- upload_artifacts ---------------------------------------------------------


def test_upload_maps_409_to_a_concurrency_message(config: CloudConfig, tarball: Path) -> None:
    client = _client_with(
        config,
        lambda request: httpx.Response(
            409,
            json={
                "statusCode": "409",
                "error": "Duplicate",
                "message": "The resource already exists",
            },
        ),
    )

    with pytest.raises(CloudApiError) as excinfo:
        client.upload_artifacts(UPLOAD_URL, tarball)

    # The raw storage body ("The resource already exists") is meaningless to a dbt
    # engineer and must never reach them.
    assert "already uploading this version" in str(excinfo.value)
    assert "resource already exists" not in str(excinfo.value)


def test_upload_reports_progress(config: CloudConfig, tarball: Path) -> None:
    client = _client_with(config, lambda request: httpx.Response(200, json={}))
    advanced: list[int] = []

    client.upload_artifacts(UPLOAD_URL, tarball, on_progress=advanced.append)

    assert sum(advanced) == tarball.stat().st_size


def test_upload_retries_once_then_gives_a_readable_error(
    config: CloudConfig, tarball: Path
) -> None:
    attempts = {"n": 0}

    def always_timeout(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        raise httpx.ConnectTimeout("too slow")

    client = _client_with(config, always_timeout)

    with pytest.raises(CloudApiError, match="Upload interrupted"):
        client.upload_artifacts(UPLOAD_URL, tarball)

    assert attempts["n"] == 2  # one attempt plus exactly one retry


def test_upload_succeeds_on_the_retry(config: CloudConfig, tarball: Path) -> None:
    attempts = {"n": 0}

    def fail_then_succeed(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise httpx.ReadTimeout("blip")
        return httpx.Response(200, json={})

    client = _client_with(config, fail_then_succeed)

    client.upload_artifacts(UPLOAD_URL, tarball)  # must not raise

    assert attempts["n"] == 2


# -- finalize_publish ---------------------------------------------------------


def test_finalize_sends_the_expected_version_crosscheck(config: CloudConfig) -> None:
    seen: list[httpx.Request] = []
    client = _client_with(
        config,
        lambda request: httpx.Response(202, json={"data": {"publish_id": "pub-1"}}),
        recorder=seen,
    )

    client.finalize_publish(expected_version=4)

    assert json.loads(seen[0].content) == {"expected_version": 4}


def test_finalize_treats_already_finalized_as_success(config: CloudConfig) -> None:
    """A concurrent publish won the race, but it carries our artifact.

    Failing here would report a publish as broken when it actually landed, so the
    winner's id is returned for polling instead.
    """
    client = _client_with(
        config,
        lambda request: httpx.Response(
            409,
            json={
                "code": "PUBLISH_ALREADY_FINALIZED",
                "error": "A publish for v4 of this project was already finalized.",
                "data": {"publish_id": "pub-winner", "version": 4},
            },
        ),
    )

    result = client.finalize_publish(expected_version=4)

    assert result["data"]["publish_id"] == "pub-winner"


def test_finalize_raises_on_version_advanced(config: CloudConfig) -> None:
    client = _client_with(
        config,
        lambda request: httpx.Response(
            409,
            json={
                "code": "VERSION_ADVANCED",
                "error": (
                    "Another publish for this project completed while your artifact "
                    "was uploading (expected v4, now at v5). Re-run `docglow publish`."
                ),
            },
        ),
    )

    with pytest.raises(CloudApiError, match="completed while your artifact was uploading"):
        client.finalize_publish(expected_version=4)


def test_finalize_raises_on_artifact_not_uploaded(config: CloudConfig) -> None:
    client = _client_with(
        config,
        lambda request: httpx.Response(
            409,
            json={
                "code": "ARTIFACT_NOT_UPLOADED",
                "error": (
                    "No uploaded artifact found for v4. Request a fresh upload URL "
                    "and upload the tarball before finalizing."
                ),
            },
        ),
    )

    with pytest.raises(CloudApiError, match="No uploaded artifact found"):
        client.finalize_publish()


# -- Orchestration: _upload_and_finalize --------------------------------------


def test_full_flow_returns_the_publish_id_from_finalize(config: CloudConfig, tarball: Path) -> None:
    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/publish/upload-url":
            # Deliberately a different id than finalize returns, to prove which one
            # the caller reports.
            return httpx.Response(
                200,
                json={
                    "data": {
                        "upload_url": UPLOAD_URL,
                        "expected_version": 4,
                        "max_bytes": 52428800,
                    }
                },
            )
        if request.method == "PUT":
            return httpx.Response(200, json={})
        if request.url.path == "/api/v1/publish/finalize":
            return httpx.Response(202, json={"data": {"publish_id": "pub-final", "version": 4}})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = _client_with(config, route)

    result = _upload_and_finalize(client, tarball)

    assert result["data"]["publish_id"] == "pub-final"


def test_flow_refuses_upload_over_the_servers_max_bytes(config: CloudConfig, tarball: Path) -> None:
    """Fail immediately rather than after a doomed multi-minute upload."""
    seen: list[httpx.Request] = []
    client = _client_with(
        config,
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "upload_url": UPLOAD_URL,
                    "expected_version": 4,
                    "max_bytes": 10,  # smaller than the tarball
                }
            },
        ),
        recorder=seen,
    )

    with pytest.raises(CloudApiError, match="over the"):
        _upload_and_finalize(client, tarball)

    assert not any(r.method == "PUT" for r in seen)


def test_flow_falls_back_to_inline_upload_on_404_for_a_small_tarball(
    config: CloudConfig, tarball: Path
) -> None:
    seen: list[httpx.Request] = []

    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/publish/upload-url":
            return httpx.Response(404, text="Not Found")
        if request.url.path == "/api/v1/publish":
            return httpx.Response(202, json={"data": {"publish_id": "pub-legacy"}})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = _client_with(config, route, recorder=seen)

    result = _upload_and_finalize(client, tarball)

    assert result["data"]["publish_id"] == "pub-legacy"
    assert any(r.url.path == "/api/v1/publish" and r.method == "POST" for r in seen)


def test_flow_refuses_the_fallback_when_the_tarball_is_too_large(
    config: CloudConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Above the platform body limit the fallback is guaranteed to 413.

    Saying so is far better than letting the user watch an upload that cannot work
    and then reporting a raw FUNCTION_PAYLOAD_TOO_LARGE.
    """
    big = tmp_path / "artifacts.tar.gz"
    big.write_bytes(b"\0" * (LEGACY_UPLOAD_LIMIT_BYTES + 1))

    seen: list[httpx.Request] = []
    client = _client_with(
        config, lambda request: httpx.Response(404, text="Not Found"), recorder=seen
    )

    with pytest.raises(CloudApiError) as excinfo:
        _upload_and_finalize(client, big)

    message = str(excinfo.value)
    assert "does not support large uploads" in message
    assert "4 MB" in message
    # Crucially, it did not attempt the doomed upload.
    assert not any(r.url.path == "/api/v1/publish" for r in seen)


def test_flow_does_not_fall_back_on_a_real_refusal(config: CloudConfig, tarball: Path) -> None:
    """429/402/403/5xx are real answers, not "route missing".

    Falling back on a throttle would turn a clear retry-later into a 413.
    """
    seen: list[httpx.Request] = []
    client = _client_with(
        config,
        lambda request: httpx.Response(
            429,
            json={
                "code": "PUBLISH_RATE_LIMITED",
                "error": "Publish rate limit reached for this project.",
            },
        ),
        recorder=seen,
    )

    with pytest.raises(CloudApiError, match="rate limit reached"):
        _upload_and_finalize(client, tarball)

    assert not any(r.url.path == "/api/v1/publish" for r in seen)


# -- Transport failures surface as messages, not tracebacks -------------------


def test_unreachable_server_raises_cloud_api_error(
    config: CloudConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("docglow.cloud.client.time.sleep", lambda _s: None)

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client_with(config, refuse)

    # Nothing catches httpx errors upstream, so an unwrapped one would surface to
    # the user as a traceback.
    with pytest.raises(CloudApiError, match="Could not reach docglow Cloud"):
        client.create_upload_url()


def test_json_calls_retry_on_5xx(config: CloudConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("docglow.cloud.client.time.sleep", lambda _s: None)
    attempts = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(503, text="upstream unavailable")
        return httpx.Response(200, json={"data": {"upload_url": UPLOAD_URL, "expected_version": 1}})

    client = _client_with(config, flaky)

    assert client.create_upload_url()["expected_version"] == 1
    assert attempts["n"] == 3
