"""Init command for docglow CLI."""

from pathlib import Path

import click

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
#     high_subquery_count: 5

# profiling:
#   enabled: false
#   sample_size: 10000
#   cache: true

# ai:
#   enabled: false
#   model: claude-sonnet-4

# insights:
#   enabled: true
#   descriptions: append  # append | replace | skip

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


@click.command()
@click.option("--project-dir", type=click.Path(path_type=Path), default=".")
@click.option("--force", is_flag=True, help="Overwrite existing docglow.yml")
def init(project_dir: Path, force: bool) -> None:
    """Generate a docglow.yml configuration file."""
    from docglow.cli import console

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
