"""Tests for configuration loading."""

from docglow.config import (
    DocglowConfig,
    HealthWeights,
    LineageBadgeConfig,
    SidebarConfig,
    TableLayoutConfig,
    UiConfig,
    _build_config_from_dict,
    load_config,
)


class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, tmp_path):
        config = load_config(tmp_path)
        assert config == DocglowConfig()

    def test_loads_docglow_yml(self, tmp_path):
        (tmp_path / "docglow.yml").write_text("title: My Project\n")
        config = load_config(tmp_path)
        assert config.title == "My Project"

    def test_loads_docglow_yaml(self, tmp_path):
        (tmp_path / "docglow.yaml").write_text("title: Alt Extension\n")
        config = load_config(tmp_path)
        assert config.title == "Alt Extension"

    def test_yml_takes_precedence_over_yaml(self, tmp_path):
        (tmp_path / "docglow.yml").write_text("title: YML\n")
        (tmp_path / "docglow.yaml").write_text("title: YAML\n")
        config = load_config(tmp_path)
        assert config.title == "YML"

    def test_invalid_yaml_returns_defaults(self, tmp_path):
        (tmp_path / "docglow.yml").write_text("just a string\n")
        config = load_config(tmp_path)
        assert config == DocglowConfig()


class TestBuildConfigFromDict:
    def test_empty_dict(self):
        config = _build_config_from_dict({})
        assert config.title == "docglow"
        assert config.health.weights == HealthWeights()
        assert config.enable_erd is False

    def test_enable_erd_true(self):
        config = _build_config_from_dict({"enable_erd": True})
        assert config.enable_erd is True

    def test_enable_erd_false_explicit(self):
        config = _build_config_from_dict({"enable_erd": False})
        assert config.enable_erd is False

    def test_enable_erd_truthy_coerces(self):
        # YAML strings like "yes" parse to True; other truthy values should also work.
        config = _build_config_from_dict({"enable_erd": "yes"})
        assert config.enable_erd is True

    def test_custom_health_weights(self):
        config = _build_config_from_dict(
            {
                "health": {
                    "weights": {"documentation": 0.40, "testing": 0.30},
                },
            }
        )
        assert config.health.weights.documentation == 0.40
        assert config.health.weights.testing == 0.30
        # Unchanged defaults
        assert config.health.weights.freshness == 0.15

    def test_custom_naming_rules(self):
        config = _build_config_from_dict(
            {
                "health": {
                    "naming_rules": {"staging": "^staging_"},
                },
            }
        )
        assert config.health.naming_rules.patterns_for("staging") == ("^staging_",)

    def test_naming_rules_backwards_compat_marts(self):
        config = _build_config_from_dict(
            {
                "health": {
                    "naming_rules": {"marts_fact": "^fct_", "marts_dimension": "^dim_"},
                },
            }
        )
        assert config.health.naming_rules.patterns_for("marts") == ("^fct_", "^dim_")

    def test_naming_rules_arbitrary_layer(self):
        config = _build_config_from_dict(
            {
                "health": {
                    "naming_rules": {"base": "^base_", "staging": "^stg_"},
                },
            }
        )
        assert config.health.naming_rules.patterns_for("base") == ("^base_",)
        assert config.health.naming_rules.patterns_for("staging") == ("^stg_",)

    def test_custom_complexity_thresholds(self):
        config = _build_config_from_dict(
            {
                "health": {
                    "complexity": {"high_sql_lines": 300, "high_join_count": 12},
                },
            }
        )
        assert config.health.complexity.high_sql_lines == 300
        assert config.health.complexity.high_join_count == 12
        assert config.health.complexity.high_cte_count == 10

    def test_profiling_config(self):
        config = _build_config_from_dict(
            {
                "profiling": {
                    "enabled": True,
                    "sample_size": 5000,
                    "exclude_schemas": ["raw", "scratch"],
                },
            }
        )
        assert config.profiling.enabled is True
        assert config.profiling.sample_size == 5000
        assert config.profiling.exclude_schemas == ("raw", "scratch")

    def test_ai_config(self):
        config = _build_config_from_dict(
            {
                "ai": {
                    "enabled": True,
                    "max_requests_per_session": 50,
                },
            }
        )
        assert config.ai.enabled is True
        assert config.ai.max_requests_per_session == 50

    def test_slim_option(self):
        config = _build_config_from_dict({"slim": True})
        assert config.slim is True

    def test_slim_default_false(self):
        config = _build_config_from_dict({})
        assert config.slim is False

    def test_unknown_keys_ignored(self):
        config = _build_config_from_dict(
            {
                "title": "My Docs",
                "unknown_key": "whatever",
                "health": {"weights": {"unknown_weight": 0.5}},
            }
        )
        assert config.title == "My Docs"

    def test_full_config(self):
        config = _build_config_from_dict(
            {
                "version": 1,
                "title": "Acme Analytics",
                "theme": "dark",
                "health": {
                    "weights": {"documentation": 0.30, "testing": 0.20},
                    "naming_rules": {"staging": "^stg_"},
                    "complexity": {"high_sql_lines": 150},
                },
                "profiling": {"enabled": True, "sample_size": 1000},
                "ai": {"enabled": True},
            }
        )
        assert config.title == "Acme Analytics"
        assert config.theme == "dark"
        assert config.health.weights.documentation == 0.30
        assert config.health.naming_rules.patterns_for("staging") == ("^stg_",)
        assert config.health.complexity.high_sql_lines == 150
        assert config.profiling.enabled is True
        assert config.profiling.sample_size == 1000
        assert config.ai.enabled is True

    def test_invalid_regex_in_naming_rules_is_skipped(self):
        """Invalid regex patterns should log a warning and be skipped."""
        config = _build_config_from_dict(
            {
                "health": {
                    "naming_rules": {
                        "staging": "[invalid(",  # bad regex
                        "intermediate": "^int_",  # valid
                    },
                },
            }
        )
        # Invalid regex is skipped entirely
        assert config.health.naming_rules.patterns_for("staging") is None
        # Valid regex is kept
        assert config.health.naming_rules.patterns_for("intermediate") == ("^int_",)


class TestUiConfig:
    def test_defaults_when_ui_section_absent(self):
        config = _build_config_from_dict({})
        assert config.ui == UiConfig()
        assert config.ui.lineage_badge == LineageBadgeConfig()
        assert config.ui.sidebar == SidebarConfig()
        assert config.ui.table_layout == TableLayoutConfig()
        assert config.ui.lineage_badge.abbreviation == "smart"
        assert config.ui.lineage_badge.max_model_chars == 30
        assert config.ui.lineage_badge.max_column_chars == 22

    def test_custom_abbreviation_and_limits(self):
        config = _build_config_from_dict(
            {
                "ui": {
                    "lineage_badge": {
                        "abbreviation": "truncate",
                        "max_model_chars": 18,
                        "max_column_chars": 14,
                    }
                }
            }
        )
        assert config.ui.lineage_badge.abbreviation == "truncate"
        assert config.ui.lineage_badge.max_model_chars == 18
        assert config.ui.lineage_badge.max_column_chars == 14

    def test_invalid_abbreviation_falls_back_to_smart(self):
        config = _build_config_from_dict({"ui": {"lineage_badge": {"abbreviation": "chonky"}}})
        assert config.ui.lineage_badge.abbreviation == "smart"

    def test_non_positive_max_chars_uses_default(self):
        config = _build_config_from_dict(
            {"ui": {"lineage_badge": {"max_model_chars": 0, "max_column_chars": -5}}}
        )
        assert config.ui.lineage_badge.max_model_chars == 30
        assert config.ui.lineage_badge.max_column_chars == 22

    def test_non_integer_max_chars_uses_default(self):
        config = _build_config_from_dict({"ui": {"lineage_badge": {"max_model_chars": "wide"}}})
        assert config.ui.lineage_badge.max_model_chars == 30

    def test_accepts_all_four_strategies(self):
        for strategy in ("smart", "truncate", "middle", "none"):
            config = _build_config_from_dict({"ui": {"lineage_badge": {"abbreviation": strategy}}})
            assert config.ui.lineage_badge.abbreviation == strategy

    def test_custom_sidebar_layout(self):
        config = _build_config_from_dict(
            {
                "ui": {
                    "sidebar": {
                        "default_width": 320,
                        "min_width": 220,
                        "max_width": 560,
                        "resizable": False,
                    }
                }
            }
        )
        assert config.ui.sidebar == SidebarConfig(
            default_width=320,
            min_width=220,
            max_width=560,
            resizable=False,
        )

    def test_sidebar_default_width_is_clamped_to_bounds(self):
        config = _build_config_from_dict(
            {"ui": {"sidebar": {"default_width": 120, "min_width": 220, "max_width": 560}}}
        )
        assert config.ui.sidebar.default_width == 220

    def test_sidebar_max_width_cannot_be_less_than_min_width(self):
        config = _build_config_from_dict(
            {"ui": {"sidebar": {"default_width": 260, "min_width": 360, "max_width": 240}}}
        )
        assert config.ui.sidebar.min_width == 360
        assert config.ui.sidebar.max_width == 360
        assert config.ui.sidebar.default_width == 360

    def test_sidebar_resizable_accepts_string_boolean(self):
        config = _build_config_from_dict({"ui": {"sidebar": {"resizable": "off"}}})
        assert config.ui.sidebar.resizable is False

    def test_custom_table_layout(self):
        config = _build_config_from_dict(
            {
                "ui": {
                    "table_layout": {
                        "mode": "scroll",
                        "min_width": 1040,
                        "content_sized_columns": ["column", "lineage", "tests"],
                        "content_sized_max_width": 420,
                    }
                }
            }
        )
        assert config.ui.table_layout == TableLayoutConfig(
            mode="scroll",
            min_width=1040,
            content_sized_columns=("column", "lineage", "tests"),
            content_sized_max_width=420,
        )

    def test_invalid_table_layout_mode_falls_back_to_auto(self):
        config = _build_config_from_dict({"ui": {"table_layout": {"mode": "squish"}}})
        assert config.ui.table_layout.mode == "auto"

    def test_invalid_table_min_width_is_ignored(self):
        config = _build_config_from_dict({"ui": {"table_layout": {"min_width": -10}}})
        assert config.ui.table_layout.min_width is None

    def test_table_layout_content_sized_columns_are_normalized(self):
        config = _build_config_from_dict(
            {
                "ui": {
                    "table_layout": {
                        "content_sized_columns": ["Column", "type", "column", "", 12],
                    }
                }
            }
        )
        assert config.ui.table_layout.content_sized_columns == ("column", "type")
