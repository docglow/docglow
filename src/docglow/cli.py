"""CLI entry point for docglow."""

import logging
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from docglow import __version__

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False, show_path=False)],
    )


@click.group()
@click.version_option(version=__version__, prog_name="docglow")
def cli() -> None:
    """docglow: Next-generation dbt documentation site generator."""


@cli.command()
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
    verbose: bool,
    fail_under: float | None,
) -> None:
    """Generate the documentation site."""
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

    # Security warning for AI mode
    if ai:
        err_console = Console(stderr=True)
        err_console.print(
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
            ai_key=ai_key,
            title=title,
            select=select,
            exclude=exclude,
        )
        console.print(f"\n[bold green]Site generated at {output_path}[/bold green]")
        if static:
            console.print("  Single-file mode: open index.html directly in a browser")
        else:
            console.print("  Run [bold]docglow serve[/bold] to view locally")

        if fail_under is not None:
            from docglow.artifacts.loader import load_artifacts as _load_artifacts
            from docglow.generator.data import build_docglow_data as _build_data

            _artifacts = _load_artifacts(project_dir, target_dir)
            _data = _build_data(_artifacts)
            _score = _data["health"]["score"]["overall"]

            if _score < fail_under:
                console.print(
                    f"\n[bold red]Health score {_score:.0f} is below "
                    f"threshold {fail_under:.0f}[/bold red]"
                )
                raise SystemExit(1)
            else:
                console.print(
                    f"\n[bold green]Health score: {_score:.0f} "
                    f"(threshold: {fail_under:.0f})[/bold green]"
                )
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


@cli.command()
@click.option("--project-dir", type=click.Path(exists=True, path_type=Path), default=".")
@click.option("--target-dir", type=click.Path(path_type=Path), default=None)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "markdown"]),
    default="table",
)
@click.option("--select", type=str, default=None)
@click.option(
    "--fail-under",
    type=float,
    default=None,
    help="Exit with code 1 if health score is below this threshold (0-100)",
)
def health(
    project_dir: Path,
    target_dir: Path | None,
    output_format: str,
    select: str | None,
    fail_under: float | None,
) -> None:
    """Show project health score."""
    import json

    from rich.table import Table

    from docglow.artifacts.loader import ArtifactLoadError, load_artifacts
    from docglow.generator.data import build_docglow_data

    try:
        artifacts = load_artifacts(project_dir, target_dir)
    except ArtifactLoadError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from e

    # Build data to get transformed models/sources
    data = build_docglow_data(artifacts)
    health_data = data["health"]
    score = health_data["score"]

    if output_format == "json":
        console.print(json.dumps(health_data, indent=2))
        if fail_under is not None and score["overall"] < fail_under:
            console.print(
                f"\n[bold red]Health score {score['overall']:.0f} is below "
                f"threshold {fail_under:.0f}[/bold red]"
            )
            raise SystemExit(1)
        return

    # Table or markdown output
    grade_color = {
        "A": "green",
        "B": "blue",
        "C": "yellow",
        "D": "red",
        "F": "bold red",
    }.get(score["grade"], "white")

    console.print()
    console.print("[bold]docglow Project Health[/bold]")
    overall = f"{score['overall']:.0f}/100 ({score['grade']})"
    console.print(f"  Overall Score: [{grade_color}]{overall}[/{grade_color}]")
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
        "No monitored sources" if score["freshness"] == 100.0 else "",
    )
    table.add_row(
        "Model Complexity",
        f"{score['complexity']:.0f}",
        f"{health_data['complexity']['high_count']} high-complexity models",
    )
    table.add_row(
        "Naming Conventions",
        f"{score['naming']:.0f}",
        f"{health_data['naming']['compliant_count']}"
        f"/{health_data['naming']['total_checked']} compliant",
    )
    table.add_row(
        "Orphan Detection",
        f"{score['orphans']:.0f}",
        f"{len(health_data['orphans'])} orphan models",
    )

    console.print(table)
    console.print()

    if fail_under is not None and score["overall"] < fail_under:
        console.print(
            f"\n[bold red]Health score {score['overall']:.0f} is below "
            f"threshold {fail_under:.0f}[/bold red]"
        )
        raise SystemExit(1)


@cli.command()
@click.option("--project-dir", type=click.Path(exists=True, path_type=Path), default=".")
@click.option("--target-dir", type=click.Path(path_type=Path), default=None)
@click.option("--adapter", type=click.Choice(["duckdb", "postgres", "snowflake"]), required=True)
@click.option(
    "--connection",
    type=str,
    required=True,
    help="Connection string or path (e.g., path/to/db.duckdb)",
)
@click.option("--sample-size", type=int, default=None, help="Max rows to sample per model")
@click.option("--no-cache", is_flag=True, help="Skip profile caching")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for profiles.json",
)
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

    from docglow.artifacts.loader import ArtifactLoadError, load_artifacts
    from docglow.generator.data import build_docglow_data
    from docglow.profiler.engine import ProfilerError, profile_models

    try:
        artifacts = load_artifacts(project_dir, target_dir)
    except ArtifactLoadError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from e

    data = build_docglow_data(artifacts)
    models = data["models"]

    connection_params = _parse_connection(adapter, connection)
    output_dir = output or (project_dir / "target" / "docglow")
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


@cli.command()
@click.option(
    "--token",
    envvar="DOCGLOW_TOKEN",
    default=None,
    help="API token (or set DOCGLOW_TOKEN env var)",
)
@click.option("--project-dir", type=click.Path(exists=True, path_type=Path), default=".")
@click.option("--target-dir", type=click.Path(path_type=Path), default=None)
@click.option("--no-wait", is_flag=True, help="Don't wait for processing to complete")
@click.option("--verbose", is_flag=True)
def publish(
    token: str | None,
    project_dir: Path,
    target_dir: Path | None,
    no_wait: bool,
    verbose: bool,
) -> None:
    """Publish documentation to docglow.dev."""
    _setup_logging(verbose)

    try:
        from docglow.cloud.config import load_cloud_config
        from docglow.cloud.publish import run_publish
    except ImportError:
        console.print(
            "[bold red]Error:[/bold red] Cloud features require httpx. "
            "Install with: [bold]pip install docglow\\[cloud][/bold]"
        )
        raise SystemExit(1)

    config = load_cloud_config()
    if token:
        from dataclasses import replace

        config = replace(config, token=token)

    if not config.token:
        console.print(
            "[bold red]Error:[/bold red] No API token found. "
            "Set DOCGLOW_TOKEN env var or run [bold]docglow login[/bold]."
        )
        raise SystemExit(1)

    try:
        from docglow.cloud.client import CloudApiError

        result = run_publish(config, project_dir, target_dir, no_wait=no_wait)
        status = result.get("status", "unknown")

        if status == "complete":
            site_url = result.get("site_url", "")
            health_score = result.get("health_score")
            console.print("\n[bold green]Published successfully![/bold green]")
            if site_url:
                console.print(f"  Site: {site_url}")
            if health_score is not None:
                console.print(f"  Health score: {health_score}")
        else:
            publish_id = result.get("publish_id", "")
            console.print("\n[bold blue]Upload complete[/bold blue]")
            console.print(f"  Publish ID: {publish_id}")
            console.print(f"  Status: {status}")
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from e
    except CloudApiError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from e


@cli.command()
@click.option("--token", type=str, default=None, help="API token for non-interactive auth")
def login(token: str | None) -> None:
    """Authenticate with docglow.dev."""
    from docglow.cloud.auth import store_token

    if token:
        store_token(token)
        console.print("[bold green]Token saved successfully.[/bold green]")
        return

    console.print("Interactive browser login is not yet available.")
    console.print("Use [bold]docglow login --token YOUR_TOKEN[/bold] instead.")
    console.print("Get your token at [bold]https://app.docglow.dev/settings/tokens[/bold]")


@cli.command()
@click.option("--token", envvar="DOCGLOW_TOKEN", default=None)
@click.option("--verbose", is_flag=True)
def status(token: str | None, verbose: bool) -> None:
    """Check docglow Cloud publish status and site health."""
    _setup_logging(verbose)

    try:
        from docglow.cloud.client import CloudApiError, CloudClient
        from docglow.cloud.config import load_cloud_config
    except ImportError:
        console.print(
            "[bold red]Error:[/bold red] Cloud features require httpx. "
            "Install with: [bold]pip install docglow\\[cloud][/bold]"
        )
        raise SystemExit(1)

    config = load_cloud_config()
    if token:
        from dataclasses import replace

        config = replace(config, token=token)

    if not config.token:
        console.print(
            "[bold red]Error:[/bold red] No API token found. "
            "Set DOCGLOW_TOKEN env var or run [bold]docglow login[/bold]."
        )
        raise SystemExit(1)

    client = CloudClient(config)
    try:
        info = client.get_workspace_info()
        console.print(f"\n[bold]Workspace:[/bold] {info.get('name', 'Unknown')}")
        console.print(f"  Slug: {info.get('slug', '')}")
        console.print(f"  Tier: {info.get('subscription_tier', 'free')}")
        if info.get("latest_health_score") is not None:
            console.print(f"  Health: {info['latest_health_score']}")
        if info.get("site_url"):
            console.print(f"  Site: {info['site_url']}")
    except CloudApiError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from e
    finally:
        client.close()


@cli.command()
def setup() -> None:
    """Interactive setup wizard for docglow Cloud."""
    from docglow.cloud.config import load_cloud_config, save_cloud_config

    config = load_cloud_config()

    console.print("[bold]docglow Cloud Setup[/bold]\n")

    if config.token:
        console.print("  Token: [green]configured[/green]")
    else:
        console.print("  Token: [yellow]not set[/yellow]")
        token = click.prompt("  Enter your API token", default="", show_default=False)
        if token:
            save_cloud_config(token=token)

    workspace = click.prompt(
        "  Workspace slug",
        default=config.workspace_slug or "",
        show_default=bool(config.workspace_slug),
    )
    project = click.prompt(
        "  Project slug",
        default=config.project_slug or "",
        show_default=bool(config.project_slug),
    )

    save_cloud_config(workspace_slug=workspace, project_slug=project)
    console.print("\n[bold green]Setup complete![/bold green]")
    console.print("  Config saved to ~/.docglow/config.json")


INIT_TEMPLATE = """\
# docglow.yml — Configuration for docglow documentation generator
# All settings are optional. Docglow works out of the box without this file.
# Uncomment and modify any settings you want to customize.

# version: 1
# title: "My dbt Project"
# theme: auto  # auto | light | dark

# health:
#   weights:
#     documentation: 0.25
#     testing: 0.25
#     freshness: 0.15
#     complexity: 0.15
#     naming: 0.10
#     orphans: 0.10
#   naming_rules:
#     staging: "^stg_"
#     intermediate: "^int_"
#     marts_fact: "^fct_"
#     marts_dimension: "^dim_"
#   complexity:
#     high_sql_lines: 200
#     high_join_count: 8
#     high_cte_count: 10

# profiling:
#   enabled: false
#   sample_size: 10000
#   cache: true

# ai:
#   enabled: false
#   model: claude-sonnet-4-20250514

# lineage_layers:
#   layers:
#     - name: source
#       rank: 0
#       color: "#dcfce7"
#     - name: staging
#       rank: 1
#       color: "#dbeafe"
#     - name: intermediate
#       rank: 2
#       color: "#fef3c7"
#     - name: mart
#       rank: 3
#       color: "#fce7f3"
#     - name: exposure
#       rank: 4
#       color: "#f3e8ff"
"""


@cli.command()
@click.option("--project-dir", type=click.Path(path_type=Path), default=".")
@click.option("--force", is_flag=True, help="Overwrite existing docglow.yml")
def init(project_dir: Path, force: bool) -> None:
    """Generate a docglow.yml configuration file."""
    for name in ("docglow.yml", "docglow.yaml"):
        if (project_dir / name).exists() and not force:
            console.print(
                f"[bold yellow]{name}[/bold yellow] already exists in {project_dir}. "
                "Use [bold]--force[/bold] to overwrite."
            )
            return

    config_path = project_dir / "docglow.yml"
    config_path.write_text(INIT_TEMPLATE, encoding="utf-8")
    console.print(
        f"[bold green]Created {config_path}[/bold green] — "
        "all settings are optional, edit as needed."
    )


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
