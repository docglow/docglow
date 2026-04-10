"""Serve command for docglow CLI."""

from pathlib import Path

import click


def _format_size(size_bytes: int) -> str:
    """Format byte count to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


@click.command()
@click.option("--port", type=int, default=8081)
@click.option("--host", type=str, default="127.0.0.1")
@click.option("--open/--no-open", default=True, help="Auto-open browser")
@click.option("--dir", "serve_dir", type=click.Path(path_type=Path), default=None)
@click.option("--watch", is_flag=True, help="Watch for artifact changes and auto-rebuild")
@click.option("--project-dir", type=click.Path(exists=True, path_type=Path), default=".")
@click.option("--verbose", is_flag=True, help="Enable debug logging")
def serve(
    port: int,
    host: str,
    open: bool,
    serve_dir: Path | None,
    watch: bool,
    project_dir: Path,
    verbose: bool,
) -> None:
    """Serve the documentation site locally."""
    from docglow.cli import _setup_logging, console

    _setup_logging(verbose)

    resolved_dir = serve_dir or Path("target/docglow")
    if not resolved_dir.exists():
        console.print(
            f"[bold red]Error:[/bold red] Directory {resolved_dir} not found. "
            "Run [bold]docglow generate[/bold] first."
        )
        raise SystemExit(1)

    # Show file info
    files = list(resolved_dir.iterdir())
    file_count = len(files)
    console.print(f"\n[bold]docglow[/bold] Serving {file_count} files from {resolved_dir}")

    # Check for data file and warn if large
    data_file = resolved_dir / "docglow-data.json"
    if data_file.exists():
        data_size = data_file.stat().st_size
        size_str = _format_size(data_size)
        console.print(f"  Data: docglow-data.json ({size_str})")
        if data_size > 15 * 1024 * 1024:  # > 15 MB
            console.print(
                f"  [yellow]Warning:[/yellow] Large data file ({size_str}). "
                "Browser may be slow to load."
            )
            console.print(
                "  Tip: Use [bold]--static[/bold] mode or [bold]--slim[/bold] to reduce file size."
            )

    console.print(f"  Local: [bold cyan]http://{host}:{port}[/bold cyan]")
    if verbose:
        console.print("  Verbose: request logging enabled")
    console.print("  Press [bold]Ctrl+C[/bold] to stop\n")

    if watch:
        from docglow.server.watcher import start_watcher

        start_watcher(project_dir, resolved_dir, console)

    from docglow.server.dev import start_server

    start_server(resolved_dir, host=host, port=port, open_browser=open)
