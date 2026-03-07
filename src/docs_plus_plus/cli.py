"""CLI entry point for docs-plus-plus."""

import logging
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from docs_plus_plus import __version__

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False, show_path=False)],
    )


@click.group()
@click.version_option(version=__version__, prog_name="docs-plus-plus")
def cli() -> None:
    """docs-plus-plus: Next-generation dbt documentation site generator."""


@cli.command()
@click.option("--project-dir", type=click.Path(exists=True, path_type=Path), default=".")
@click.option("--target-dir", type=click.Path(path_type=Path), default=None)
@click.option("--output-dir", type=click.Path(path_type=Path), default=None)
@click.option("--profile/--no-profile", default=False, help="Enable column profiling")
@click.option("--profile-adapter", type=click.Choice(["duckdb", "postgres", "snowflake"]), default=None)
@click.option("--profile-connection", type=str, default=None, help="Connection string or DB path")
@click.option("--profile-sample-size", type=int, default=None)
@click.option("--profile-no-cache", is_flag=True, help="Skip profile caching")
@click.option("--select", type=str, default=None, help="Only include matching models")
@click.option("--exclude", type=str, default=None, help="Exclude matching models")
@click.option("--static", is_flag=True, help="Bundle everything into single index.html")
@click.option("--ai", is_flag=True, help="Enable AI chat panel")
@click.option("--title", type=str, default=None, help="Custom site title")
@click.option("--theme", type=click.Choice(["light", "dark", "auto"]), default="auto")
@click.option("--verbose", is_flag=True)
def generate(
    project_dir: Path,
    target_dir: Path | None,
    output_dir: Path | None,
    profile: bool,
    profile_adapter: str | None,
    profile_connection: str | None,
    profile_sample_size: int | None,
    profile_no_cache: bool,
    select: str | None,
    exclude: str | None,
    static: bool,
    ai: bool,
    title: str | None,
    theme: str,
    verbose: bool,
) -> None:
    """Generate the documentation site."""
    _setup_logging(verbose)

    from docs_plus_plus.artifacts.loader import ArtifactLoadError
    from docs_plus_plus.generator.site import generate_site

    # Parse profiling connection params
    profiling_connection = None
    if profile and profile_adapter and profile_connection:
        profiling_connection = _parse_connection(profile_adapter, profile_connection)

    try:
        output_path = generate_site(
            project_dir=project_dir,
            target_dir=target_dir,
            output_dir=output_dir,
            static=static,
            profiling_enabled=profile,
            profiling_adapter=profile_adapter,
            profiling_connection=profiling_connection,
            profiling_sample_size=profile_sample_size,
            profiling_cache=not profile_no_cache,
            ai_enabled=ai,
            title=title,
        )
        console.print(f"\n[bold green]Site generated at {output_path}[/bold green]")
        if static:
            console.print("  Single-file mode: open index.html directly in a browser")
        else:
            console.print("  Run [bold]docs-plus-plus serve[/bold] to view locally")
    except ArtifactLoadError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from e
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from e


@cli.command()
@click.option("--port", type=int, default=8081)
@click.option("--host", type=str, default="127.0.0.1")
@click.option("--open/--no-open", default=True, help="Auto-open browser")
@click.option("--dir", "serve_dir", type=click.Path(path_type=Path), default=None)
def serve(port: int, host: str, open: bool, serve_dir: Path | None) -> None:
    """Serve the documentation site locally."""
    from docs_plus_plus.server.dev import start_server

    resolved_dir = serve_dir or Path("target/datum")
    if not resolved_dir.exists():
        console.print(
            f"[bold red]Error:[/bold red] Directory {resolved_dir} not found. "
            "Run [bold]docs-plus-plus generate[/bold] first."
        )
        raise SystemExit(1)

    start_server(resolved_dir, host=host, port=port, open_browser=open)


@cli.command()
@click.option("--project-dir", type=click.Path(exists=True, path_type=Path), default=".")
@click.option("--target-dir", type=click.Path(path_type=Path), default=None)
@click.option("--format", "output_format", type=click.Choice(["table", "json", "markdown"]), default="table")
@click.option("--select", type=str, default=None)
def health(
    project_dir: Path,
    target_dir: Path | None,
    output_format: str,
    select: str | None,
) -> None:
    """Show project health score."""
    import json

    from rich.table import Table

    from docs_plus_plus.analyzer.health import compute_health, health_to_dict
    from docs_plus_plus.artifacts.loader import ArtifactLoadError, load_artifacts
    from docs_plus_plus.generator.data import build_datum_data

    try:
        artifacts = load_artifacts(project_dir, target_dir)
    except ArtifactLoadError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from e

    # Build data to get transformed models/sources
    datum = build_datum_data(artifacts)
    health_data = datum["health"]
    score = health_data["score"]

    if output_format == "json":
        console.print(json.dumps(health_data, indent=2))
        return

    # Table or markdown output
    grade_color = {
        "A": "green", "B": "blue", "C": "yellow", "D": "red", "F": "bold red",
    }.get(score["grade"], "white")

    console.print()
    console.print(f"[bold]docs-plus-plus Project Health[/bold]")
    console.print(f"  Overall Score: [{grade_color}]{score['overall']:.0f}/100 ({score['grade']})[/{grade_color}]")
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Category", style="bold")
    table.add_column("Score", justify="right")
    table.add_column("Details")

    cov = health_data["coverage"]
    table.add_row(
        "Documentation",
        f"{score['documentation']:.0f}",
        f"Models: {cov['models_documented']['covered']}/{cov['models_documented']['total']}  "
        f"Columns: {cov['columns_documented']['covered']}/{cov['columns_documented']['total']}",
    )
    table.add_row(
        "Testing",
        f"{score['testing']:.0f}",
        f"Models: {cov['models_tested']['covered']}/{cov['models_tested']['total']}  "
        f"Columns: {cov['columns_tested']['covered']}/{cov['columns_tested']['total']}",
    )
    table.add_row(
        "Source Freshness",
        f"{score['freshness']:.0f}",
        "No monitored sources" if score['freshness'] == 100.0 else "",
    )
    table.add_row(
        "Model Complexity",
        f"{score['complexity']:.0f}",
        f"{health_data['complexity']['high_count']} high-complexity models",
    )
    table.add_row(
        "Naming Conventions",
        f"{score['naming']:.0f}",
        f"{health_data['naming']['compliant_count']}/{health_data['naming']['total_checked']} compliant",
    )
    table.add_row(
        "Orphan Detection",
        f"{score['orphans']:.0f}",
        f"{len(health_data['orphans'])} orphan models",
    )

    console.print(table)
    console.print()


@cli.command()
@click.option("--project-dir", type=click.Path(exists=True, path_type=Path), default=".")
@click.option("--target-dir", type=click.Path(path_type=Path), default=None)
@click.option("--adapter", type=click.Choice(["duckdb", "postgres", "snowflake"]), required=True)
@click.option("--connection", type=str, required=True, help="Connection string or path (e.g., path/to/db.duckdb)")
@click.option("--sample-size", type=int, default=None, help="Max rows to sample per model")
@click.option("--no-cache", is_flag=True, help="Skip profile caching")
@click.option("--output", type=click.Path(path_type=Path), default=None, help="Output directory for profiles.json")
@click.option("--verbose", is_flag=True)
def profile(
    project_dir: Path,
    target_dir: Path | None,
    adapter: str,
    connection: str,
    sample_size: int | None,
    no_cache: bool,
    output: Path | None,
    verbose: bool,
) -> None:
    """Run column profiling only."""
    import json

    _setup_logging(verbose)

    from docs_plus_plus.artifacts.loader import ArtifactLoadError, load_artifacts
    from docs_plus_plus.generator.data import build_datum_data
    from docs_plus_plus.profiler.engine import ProfilerError, apply_profiles, profile_models

    try:
        artifacts = load_artifacts(project_dir, target_dir)
    except ArtifactLoadError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from e

    datum = build_datum_data(artifacts)
    models = datum["models"]

    connection_params = _parse_connection(adapter, connection)
    output_dir = output or (project_dir / "target" / "datum")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        profiles = profile_models(
            models,
            adapter=adapter,
            connection_params=connection_params,
            sample_size=sample_size,
            cache_dir=output_dir if not no_cache else None,
            use_cache=not no_cache,
        )
    except ProfilerError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from e

    # Count stats
    total_cols = sum(len(p) for p in profiles.values())
    console.print(
        f"\n[bold green]Profiled {len(profiles)} models, {total_cols} columns[/bold green]"
    )

    # Write profiles to standalone file
    profiles_path = output_dir / "profiles.json"
    profiles_path.write_text(json.dumps(profiles, indent=2))
    console.print(f"  Profiles saved to {profiles_path}")


def _parse_connection(adapter: str, connection: str) -> dict[str, str]:
    """Parse a connection string into params dict."""
    if adapter == "duckdb":
        return {"path": connection}
    if adapter in ("postgres", "postgresql"):
        # Expect format: host:port/dbname?user=x&password=y or just a URI
        return {"dsn": connection}
    if adapter == "snowflake":
        return {"dsn": connection}
    return {"dsn": connection}
