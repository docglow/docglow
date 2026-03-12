"""Tests for configuration loading."""

from docglow.config import (
    DocglowConfig,
    HealthWeights,
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
        assert config.health.naming_rules.staging == "^staging_"
        assert config.health.naming_rules.marts_fact == "^fct_"

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
        assert config.health.naming_rules.staging == "^stg_"
        assert config.health.complexity.high_sql_lines == 150
        assert config.profiling.enabled is True
        assert config.profiling.sample_size == 1000
        assert config.ai.enabled is True
