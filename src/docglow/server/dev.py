"""Local development server for serving the generated documentation site."""

from __future__ import annotations

import functools
import logging
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

logger = logging.getLogger(__name__)


def start_server(
    directory: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8081,
    open_browser: bool = True,
) -> None:
    """Start a local HTTP server to serve the documentation site.

    Args:
        directory: Directory containing the generated site.
        host: Host to bind the server to.
        port: Port to listen on.
        open_browser: Whether to auto-open the browser.
    """
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = HTTPServer((host, port), handler)

    url = f"http://{host}:{port}"
    logger.debug("Server bound to %s:%d, serving from %s", host, port, directory)

    if open_browser:
        try:
            webbrowser.open(url)
            logger.debug("Browser opened at %s", url)
        except Exception:
            logger.debug("Could not open browser automatically")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped")
        server.server_close()
