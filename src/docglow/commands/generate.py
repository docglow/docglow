"""Generate command for docglow CLI."""

from pathlib import Path

import click


@click.command()
@click.option("--project-dir", type=click.Path(exists=True, path_type=Path), default=".")
@click.option("--target-dir", type=click.Path(path_type=Path), default=None)
@click.option("--output-dir", type=click.Path(path_type=Path), default=None)
@click.option("--profile/--no-profile", default=False, help="Enable column profiling")
@click.option(
    "--profile-adapter",
    type=click.Choice(["duckdb", "postgres", "snowflake"]),
    default=None,
)
@click.option("--profile-connection", type=str, default=None, help="Connection string or DB path")
@click.option("--profile-sample-size", type=int, default=None)
@click.option("--profile-no-cache", is_flag=True, help="Skip profile caching")
@click.option("--select", type=str, default=None, help="Only include matching models")
@click.option("--exclude", type=str, default=None, help="Exclude matching models")
@click.option("--static", is_flag=True, help="Bundle everything into single index.html")
@click.option("--ai", is_flag=True, help="Enable AI chat panel")
@click.option(
    "--ai-key",
    type=str,
    default=None,
    help="Anthropic API key (or set ANTHROPIC_API_KEY env var)",
)
@click.option("--title", type=str, default=None, help="Custom site title")
@click.option("--theme", type=click.Choice(["light", "dark", "auto"]), default="auto")
@click.option(
    "--skip-column-lineage",
    is_flag=True,
    default=False,
    help="Skip column-level lineage analysis (enabled by default)",
)
@click.option(
    "--column-lineage-select",
    type=str,
    default=None,
    help="Only analyze column lineage for this model and its dependencies "
    "(e.g. fct_orders, +fct_orders, fct_orders+)",
)
@click.option(
    "--column-lineage-depth",
    type=int,
    default=None,
    help="Max hops from the selected model (default: unlimited)",
)
@click.option(
    "--include-packages",
    is_flag=True,
    default=False,
    help="Include dbt package models in lineage graph",
)
@click.option(
    "--slim",
    is_flag=True,
    default=False,
    help="Omit raw and compiled SQL from output to reduce file size "
    "(does not affect computation time)",
)
@click.option(
    "--head-script",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to an HTML file whose contents are injected into <head> (e.g. analytics snippet)",
)
@click.option(
    "--workers",
    type=int,
    default=None,
    help="Max parallel workers for column lineage (default: auto)",
)
@click.option("--verbose", is_flag=True)
@click.option(
    "--fail-under",
    type=float,
    default=None,
    help="Exit with code 1 if health score is below this threshold (0-100)",
)
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
    ai_key: str | None,
    title: str | None,
    theme: str,
    skip_column_lineage: bool,
    column_lineage_select: str | None,
    column_lineage_depth: int | None,
    include_packages: bool,
    slim: bool,
    head_script: Path | None,
    workers: int | None,
    verbose: bool,
    fail_under: float | None,
) -> None:
    """Generate the documentation site."""
    from docglow.cli import _parse_connection, _setup_logging, console

    _setup_logging(verbose)

    from docglow.artifacts.loader import ArtifactLoadError
    from docglow.config import load_config
    from docglow.generator.site import generate_site

    # Load config file (docglow.yml)
    config = load_config(project_dir)

    # CLI flags override config file values
    if not ai and config.ai.enabled:
        ai = True
    if ai_key:
        ai = True  # --ai-key implies --ai
    if not title and config.title != "docglow":
        title = config.title
    if not slim and config.slim:
        slim = True

    # Resolve column lineage: on by default, off via --skip-column-lineage or config
    column_lineage = not skip_column_lineage
    if column_lineage and not config.column_lineage:
        column_lineage = False

    # --column-lineage-select overrides skip (user explicitly scoped it)
    if column_lineage_select:
        column_lineage = True

    # --column-lineage-depth requires --column-lineage-select
    if column_lineage_depth is not None and not column_lineage_select:
        console.print(
            "[bold red]Error:[/bold red] --column-lineage-depth requires --column-lineage-select"
        )
        raise SystemExit(1)

    # AI mode info
    if ai:
        console.print(
            "\n[bold blue]Info:[/bold blue] AI chat enabled. Your API key is "
            "[bold]not[/bold] embedded in the site.\n"
            "  Enter your Anthropic API key in the chat panel (it's stored "
            "in your browser's localStorage).\n",
        )

    # Parse profiling connection params
    profiling_connection = None
    if profile and profile_adapter and profile_connection:
        profiling_connection = _parse_connection(profile_adapter, profile_connection)

    try:
        output_path, health_score = generate_site(
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
            select=select,
            exclude=exclude,
            column_lineage_enabled=column_lineage,
            column_lineage_select=column_lineage_select,
            column_lineage_depth=column_lineage_depth,
            exclude_packages=not include_packages,
            slim=slim,
            head_script=head_script.read_text(encoding="utf-8") if head_script else None,
            column_lineage_workers=workers,
        )
        console.print(f"\n[bold green]Site generated at {output_path}[/bold green]")
        if static:
            console.print("  Single-file mode: open index.html directly in a browser")
        else:
            console.print("  Run [bold]docglow serve[/bold] to view locally")

        if fail_under is not None:
            if health_score < fail_under:
                console.print(
                    f"\n[bold red]Health score {health_score:.0f} is below "
                    f"threshold {fail_under:.0f}[/bold red]"
                )
                raise SystemExit(1)
            else:
                console.print(
                    f"\n[bold green]Health score: {health_score:.0f} "
                    f"(threshold: {fail_under:.0f})[/bold green]"
                )
    except ArtifactLoadError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from e
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from e
