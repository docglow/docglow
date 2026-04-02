"""Tests for the column lineage threshold warning (DOC-89)."""

from unittest.mock import patch

from docglow.generator.pipeline import PipelineContext, stage_warn_column_lineage


def _make_ctx(
    *,
    enabled: bool = True,
    select: str | None = None,
    model_count: int = 0,
    columns_per_model: int = 10,
) -> PipelineContext:
    """Create a minimal PipelineContext with fake models."""
    from unittest.mock import MagicMock

    ctx = MagicMock(spec=PipelineContext)
    ctx.column_lineage_enabled = enabled
    ctx.column_lineage_select = select

    models = {}
    for i in range(model_count):
        columns = [{"name": f"col_{j}"} for j in range(columns_per_model)]
        models[f"model.project.model_{i}"] = {"columns": columns}
    ctx.models = models

    return ctx


class TestColumnLineageWarning:
    """stage_warn_column_lineage should warn for large projects."""

    def test_no_warning_when_disabled(self) -> None:
        ctx = _make_ctx(enabled=False, model_count=100)
        with patch("docglow.generator.pipeline.Console") as mock_console_cls:
            stage_warn_column_lineage(ctx)
            mock_console_cls.assert_not_called()

    def test_no_warning_when_select_specified(self) -> None:
        ctx = _make_ctx(enabled=True, select="fct_orders", model_count=100)
        with patch("docglow.generator.pipeline.Console") as mock_console_cls:
            stage_warn_column_lineage(ctx)
            mock_console_cls.assert_not_called()

    def test_no_warning_below_threshold(self) -> None:
        ctx = _make_ctx(enabled=True, model_count=74)
        with patch("docglow.generator.pipeline.Console") as mock_console_cls:
            stage_warn_column_lineage(ctx)
            mock_console_cls.assert_not_called()

    def test_warning_at_threshold(self) -> None:
        ctx = _make_ctx(enabled=True, model_count=75, columns_per_model=5)
        with patch("docglow.generator.pipeline.Console") as mock_console_cls:
            mock_console = mock_console_cls.return_value
            stage_warn_column_lineage(ctx)
            mock_console.print.assert_called_once()
            output = mock_console.print.call_args[0][0]
            assert "75" in output
            assert "375 columns" in output
            assert "--skip-column-lineage" in output
            assert "--column-lineage-select" in output

    def test_warning_above_threshold(self) -> None:
        ctx = _make_ctx(enabled=True, model_count=200, columns_per_model=20)
        with patch("docglow.generator.pipeline.Console") as mock_console_cls:
            mock_console = mock_console_cls.return_value
            stage_warn_column_lineage(ctx)
            mock_console.print.assert_called_once()
            output = mock_console.print.call_args[0][0]
            assert "200" in output
            assert "4000 columns" in output

    def test_warning_shows_minutes_for_large_projects(self) -> None:
        ctx = _make_ctx(enabled=True, model_count=100, columns_per_model=50)
        with patch("docglow.generator.pipeline.Console") as mock_console_cls:
            mock_console = mock_console_cls.return_value
            stage_warn_column_lineage(ctx)
            output = mock_console.print.call_args[0][0]
            # 5000 columns * 2s = 10000s = 166m 40s
            assert "~166m" in output
