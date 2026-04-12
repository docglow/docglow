"""Bundle the React frontend with data into a deployable static site."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# The pre-built frontend assets are stored here in the package
STATIC_DIR = Path(__file__).parent.parent / "static"


def _find_frontend_dist() -> Path:
    """Find the built frontend assets.

    Checks two locations:
    1. The package's static/ directory (for installed packages)
    2. The frontend/dist/ directory (for development)
    """
    if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
        return STATIC_DIR

    # Development fallback: look for frontend/dist relative to project root
    dev_dist = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"
    if dev_dist.exists() and (dev_dist / "index.html").exists():
        return dev_dist

    raise FileNotFoundError(
        "Built frontend assets not found. Run 'npm run build' in the frontend/ directory first."
    )


def bundle_site(
    docglow_data: dict[str, Any],
    output_dir: Path,
    *,
    static: bool = False,
    data_only: bool = False,
    head_script: str | None = None,
) -> None:
    """Bundle the frontend with data into the output directory.

    Args:
        docglow_data: The unified data payload.
        output_dir: Directory to write output files.
        static: If True, embed data into a single index.html.
        head_script: Optional HTML/JS content to inject into <head>.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if data_only:
        data_path = output_dir / "docglow-data.json"
        data_json = json.dumps(docglow_data, separators=(",", ":"))
        data_path.write_text(data_json, encoding="utf-8")
        logger.info("Data written to %s (%d bytes)", data_path, len(data_json))
        return

    frontend_dist = _find_frontend_dist()

    if static:
        _bundle_static(docglow_data, output_dir, frontend_dist, head_script=head_script)
    else:
        _bundle_separate(docglow_data, output_dir, frontend_dist, head_script=head_script)


def _bundle_separate(
    docglow_data: dict[str, Any],
    output_dir: Path,
    frontend_dist: Path,
    *,
    head_script: str | None = None,
) -> None:
    """Bundle with data as a separate JSON file."""
    # Copy all frontend assets
    _copy_frontend_assets(frontend_dist, output_dir, head_script=head_script)

    # Write data file
    data_path = output_dir / "docglow-data.json"
    data_json = json.dumps(docglow_data, separators=(",", ":"))
    data_path.write_text(data_json, encoding="utf-8")
    logger.info("Data written to %s (%d bytes)", data_path, len(data_json))


def _bundle_static(
    docglow_data: dict[str, Any],
    output_dir: Path,
    frontend_dist: Path,
    *,
    head_script: str | None = None,
) -> None:
    """Bundle everything into a single index.html."""
    import shutil

    index_path = frontend_dist / "index.html"
    html = index_path.read_text(encoding="utf-8")

    data_json = json.dumps(docglow_data, separators=(",", ":"))
    data_script = f"<script>window.__DOCGLOW_DATA__={data_json};</script>"

    # Inject security meta tags and data script BEFORE the first <script> tag
    security_meta = (
        '<meta http-equiv="X-Content-Type-Options" content="nosniff">\n'
        '<meta name="referrer" content="strict-origin-when-cross-origin">\n'
    )
    script_pos = html.find("<script")
    if script_pos != -1:
        html = html[:script_pos] + security_meta + data_script + "\n" + html[script_pos:]
    else:
        html = html.replace("</head>", f"{security_meta}{data_script}\n</head>")

    # Inject custom head script (analytics, etc.)
    if head_script:
        html = html.replace("</head>", f"{head_script}\n</head>")

    # Inline CSS and JS assets
    html = _inline_assets(html, frontend_dist)

    # Copy favicon if present
    favicon_path = frontend_dist / "favicon.svg"
    if favicon_path.exists():
        shutil.copy2(favicon_path, output_dir / "favicon.svg")

    output_path = output_dir / "index.html"
    output_path.write_text(html, encoding="utf-8")
    logger.info("Static site written to %s (%d bytes)", output_path, len(html))


def _inject_security_meta(html: str) -> str:
    """Inject security meta tags into an HTML document."""
    security_meta = (
        '<meta http-equiv="X-Content-Type-Options" content="nosniff">\n'
        '<meta name="referrer" content="strict-origin-when-cross-origin">\n'
    )
    # Insert before the first <script> tag, or before </head>
    script_pos = html.find("<script")
    if script_pos != -1:
        return html[:script_pos] + security_meta + html[script_pos:]
    return html.replace("</head>", f"{security_meta}</head>")


def _copy_frontend_assets(
    frontend_dist: Path,
    output_dir: Path,
    *,
    head_script: str | None = None,
) -> None:
    """Copy frontend build assets to the output directory."""
    import shutil

    for item in frontend_dist.iterdir():
        dest = output_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            if item.name == "index.html":
                # Inject security meta tags into the copied index.html
                html = item.read_text(encoding="utf-8")
                html = _inject_security_meta(html)
                if head_script:
                    html = html.replace("</head>", f"{head_script}\n</head>")
                dest.write_text(html, encoding="utf-8")
            else:
                shutil.copy2(item, dest)


def _inline_assets(html: str, frontend_dist: Path) -> str:
    """Inline CSS and JS files referenced in the HTML."""
    import re

    # Inline CSS: <link rel="stylesheet" href="./assets/index-xxx.css">
    def replace_css(match: re.Match[str]) -> str:
        href = match.group(1)
        css_path = frontend_dist / href.lstrip("./")
        if css_path.exists():
            css_content = css_path.read_text(encoding="utf-8")
            return f"<style>{css_content}</style>"
        return match.group(0)

    html = re.sub(
        r'<link[^>]+href=["\'](\./assets/[^"\']+\.css)["\'][^>]*/?>',
        replace_css,
        html,
    )

    # Inline JS: <script type="module" src="./assets/index-xxx.js">
    def replace_js(match: re.Match[str]) -> str:
        src = match.group(1)
        js_path = frontend_dist / src.lstrip("./")
        if js_path.exists():
            js_content = js_path.read_text(encoding="utf-8")
            return f'<script type="module">{js_content}</script>'
        return match.group(0)

    html = re.sub(
        r'<script[^>]+src=["\'](\./assets/[^"\']+\.js)["\'][^>]*></script>',
        replace_js,
        html,
    )

    return html
