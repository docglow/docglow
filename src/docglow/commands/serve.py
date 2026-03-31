"""Serve command for docglow CLI."""

from pathlib import Path

import click


@click.command()
@click.option("--port", type=int, default=8081)
@click.option("--host", type=str, default="127.0.0.1")
@click.option("--open/--no-open", default=True, help="Auto-open browser")
@click.option("--dir", "serve_dir", type=click.Path(path_type=Path), default=None)
@click.option("--watch", is_flag=True, help="Watch for artifact changes and auto-rebuild")
@click.option("--project-dir", type=click.Path(exists=True, path_type=Path), default=".")
def serve(
    port: int,
    host: str,
    open: bool,
    serve_dir: Path | None,
    watch: bool,
    project_dir: Path,
) -> None:
    """Serve the documentation site locally."""
    from docglow.cli import console
    from docglow.server.dev import start_server

    resolved_dir = serve_dir or Path("target/docglow")
    if not resolved_dir.exists():
        console.print(
            f"[bold red]Error:[/bold red] Directory {resolved_dir} not found. "
            "Run [bold]docglow generate[/bold] first."
        )
        raise SystemExit(1)

    if watch:
        from docglow.server.watcher import start_watcher

        start_watcher(project_dir, resolved_dir, console)

    start_server(resolved_dir, host=host, port=port, open_browser=open)
