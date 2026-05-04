"""Health command for docglow CLI."""

from pathlib import Path

import click


@click.command()
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
    from docglow.cli import console
    from docglow.config import load_config
    from docglow.generator.data import build_docglow_data
    from docglow.telemetry import dispatcher as telemetry

    config = load_config(project_dir)
    loaded_manifest = None

    with telemetry.record(
        config.telemetry,
        command="health",
        shape_provider=lambda: telemetry.project_shape_from_manifest(loaded_manifest),
        features_used=(output_format,),
    ):
        try:
            artifacts = load_artifacts(project_dir, target_dir)
        except ArtifactLoadError as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise SystemExit(1) from e

        loaded_manifest = artifacts.manifest

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

        if output_format == "markdown":
            lines = [
                "## Docglow Health Report\n",
                "| Category | Score |",
                "|----------|-------|",
                f"| **Overall** | **{score['overall']:.0f}/100 ({score['grade']})** |",
                f"| Documentation | {score['documentation']:.0f} |",
                f"| Testing | {score['testing']:.0f} |",
                f"| Freshness | {score['freshness']:.0f} |",
                f"| Complexity | {score['complexity']:.0f} |",
                f"| Naming | {score['naming']:.0f} |",
                f"| Orphans | {score['orphans']:.0f} |",
            ]

            undoc = health_data["coverage"].get("undocumented_models", [])
            if undoc:
                top = sorted(
                    undoc,
                    key=lambda x: x.get("downstream_count", 0),
                    reverse=True,
                )[0]
                lines.append(
                    f"\n**{len(undoc)} undocumented model{'s' if len(undoc) != 1 else ''}** "
                    f"(highest impact: `{top['name']}` with "
                    f"{top.get('downstream_count', 0)} downstream dependents)"
                )

            naming_violations = health_data["naming"].get("violations", [])
            if naming_violations:
                count = len(naming_violations)
                lines.append(f"**{count} naming violation{'s' if count != 1 else ''}**")

            orphans = health_data["orphans"]
            if orphans:
                count = len(orphans)
                lines.append(f"**{count} orphan model{'s' if count != 1 else ''}**")

            click.echo("\n".join(lines))

            if fail_under is not None and score["overall"] < fail_under:
                console.print(
                    f"\n[bold red]Health score {score['overall']:.0f} is below "
                    f"threshold {fail_under:.0f}[/bold red]"
                )
                raise SystemExit(1)
            return

        # Table output
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
