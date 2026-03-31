"""Profile command for docglow CLI."""

from pathlib import Path

import click


@click.command()
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

    from docglow.cli import _parse_connection, _setup_logging, console

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
