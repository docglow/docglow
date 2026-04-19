"""Local development server for serving the generated documentation site."""

from __future__ import annotations

import functools
import logging
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

logger = logging.getLogger(__name__)


class _DocglowHandler(SimpleHTTPRequestHandler):
    """Custom handler with request logging and proper MIME types."""

    def log_message(self, format: str, *args: object) -> None:
        """Log HTTP requests via the module logger instead of stderr."""
        logger.info(format, *args)

    def end_headers(self) -> None:
        """Add CORS and cache headers for local dev.

        index.html and docglow-data.json get ``no-store`` so the browser
        always fetches the latest version after a regenerate.  Hashed
        assets (JS/CSS with content hashes in the filename) are immutable
        and can be cached indefinitely.
        """
        self.send_header("Access-Control-Allow-Origin", "*")

        path = self.path.split("?")[0].split("#")[0]
        if path in ("/", "/index.html", "/docglow-data.json"):
            self.send_header("Cache-Control", "no-store")
        elif "/assets/" in path:
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-cache")

        super().end_headers()


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
    handler = functools.partial(_DocglowHandler, directory=str(directory))

    try:
        server = HTTPServer((host, port), handler)
    except OSError as e:
        logger.error("Could not start server on %s:%d — %s", host, port, e)
        if "Address already in use" in str(e):
            logger.error("Try a different port: docglow serve --port 8082")
        sys.exit(1)

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
