"""File watcher for auto-rebuilding on artifact changes."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

WATCH_PATTERNS = [
    "target/manifest.json",
    "target/catalog.json",
    "target/run_results.json",
    "target/sources.json",
]

POLL_INTERVAL = 2.0  # seconds


def _get_mtimes(project_dir: Path) -> dict[str, float]:
    """Get modification times for watched artifact files."""
    mtimes: dict[str, float] = {}
    for pattern in WATCH_PATTERNS:
        path = project_dir / pattern
        if path.exists():
            mtimes[str(path)] = path.stat().st_mtime
    return mtimes


def _rebuild(project_dir: Path, output_dir: Path, console: Any) -> None:
    """Trigger a site rebuild."""
    try:
        from docglow.config import load_config
        from docglow.generator.site import generate_site

        config = load_config(project_dir)
        ai_enabled = config.ai.enabled

        generate_site(
            project_dir=project_dir,
            output_dir=output_dir,
            ai_enabled=ai_enabled,
        )
        console.print("[green]Auto-rebuild complete.[/green]")
    except Exception as e:
        console.print(f"[red]Auto-rebuild failed:[/red] {e}")


def _watch_loop(project_dir: Path, output_dir: Path, console: Any) -> None:
    """Poll for artifact changes and rebuild when detected."""
    last_mtimes = _get_mtimes(project_dir)

    while True:
        time.sleep(POLL_INTERVAL)
        current_mtimes = _get_mtimes(project_dir)

        if current_mtimes != last_mtimes:
            changed = [
                p for p in current_mtimes
                if current_mtimes.get(p) != last_mtimes.get(p)
            ]
            names = [Path(p).name for p in changed]
            console.print(f"[yellow]Detected changes in: {', '.join(names)}[/yellow]")
            _rebuild(project_dir, output_dir, console)
            last_mtimes = _get_mtimes(project_dir)


def start_watcher(project_dir: Path, output_dir: Path, console: Any) -> None:
    """Start the file watcher in a background thread."""
    console.print("[dim]Watching for artifact changes...[/dim]")
    thread = threading.Thread(
        target=_watch_loop,
        args=(project_dir, output_dir, console),
        daemon=True,
    )
    thread.start()
