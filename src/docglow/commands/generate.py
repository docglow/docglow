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
    "--column-lineage/--no-column-lineage",
    default=False,
    help="Enable column-level lineage analysis (requires sqlglot)",
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
    help="Omit raw and compiled SQL from output to reduce file size",
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
    column_lineage: bool,
    column_lineage_select: str | None,
    column_lineage_depth: int | None,
    include_packages: bool,
    slim: bool,
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

    # --column-lineage-select implies --column-lineage
    if column_lineage_select:
        column_lineage = True

    # --column-lineage-depth requires --column-lineage-select
    if column_lineage_depth is not None and not column_lineage_select:
        console.print(
            "[bold red]Error:[/bold red] --column-lineage-depth requires --column-lineage-select"
        )
        raise SystemExit(1)

    # Validate column-lineage dependency
    if column_lineage:
        try:
            import sqlglot  # noqa: F401
        except ImportError:
            console.print(
                "[bold red]Error:[/bold red] Column lineage requires sqlglot. "
                "Install with: [bold]pip install docglow\\[column-lineage][/bold]"
            )
            raise SystemExit(1)

    # Security warning for AI mode
    if ai:
        console.print(
            "\n[bold yellow]Warning:[/bold yellow] AI mode embeds your API key "
            "in the generated site.\n"
            "  This is safe for local use but do [bold]NOT[/bold] deploy this "
            "site publicly.\n"
            "  Use [bold]docglow publish[/bold] for hosted AI features with "
            "secure key management.\n",
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
            ai_key=ai_key,
            title=title,
            select=select,
            exclude=exclude,
            column_lineage_enabled=column_lineage,
            column_lineage_select=column_lineage_select,
            column_lineage_depth=column_lineage_depth,
            exclude_packages=not include_packages,
            slim=slim,
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
