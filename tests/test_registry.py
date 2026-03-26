"""Tests for TeamRegistry and YAML config loading (TEAM-01, TEAM-05)."""
from __future__ import annotations

import os
import tempfile

import pytest
import yaml

from quant_team.teams.registry import TeamRegistry, TeamConfig, AgentSpec, RiskLimits


def _write_yaml(tmpdir, filename, data):
    path = os.path.join(tmpdir, filename)
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


def test_load_yaml_config(sample_team_config_dict):
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_yaml(tmpdir, "test.yaml", sample_team_config_dict)
        registry = TeamRegistry(config_dir=tmpdir)
        config = registry.get("test-team")
        assert config.team_id == "test-team"
        assert config.name == "Test Team"
        assert config.asset_class == "stocks"
        assert len(config.agents) == 1
        assert config.agents[0].name == "TestAgent"


def test_invalid_yaml_raises():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "bad.yaml")
        with open(path, "w") as f:
            f.write("just a string, not a dict")
        with pytest.raises(ValueError, match="Expected dict"):
            TeamRegistry(config_dir=tmpdir)


def test_missing_required_field_raises():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_yaml(tmpdir, "incomplete.yaml", {"team_id": "x"})
        with pytest.raises(ValueError, match="Missing required field"):
            TeamRegistry(config_dir=tmpdir)


def test_schedule_cron_from_yaml(sample_team_config_dict):
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_yaml(tmpdir, "test.yaml", sample_team_config_dict)
        registry = TeamRegistry(config_dir=tmpdir)
        config = registry.get("test-team")
        assert config.schedule_cron == [{"hour": 9, "minute": 35}]


def test_multiple_teams_loaded():
    with tempfile.TemporaryDirectory() as tmpdir:
        team1 = {"team_id": "t1", "name": "Team 1", "asset_class": "stocks", "agents": []}
        team2 = {"team_id": "t2", "name": "Team 2", "asset_class": "crypto", "agents": []}
        _write_yaml(tmpdir, "t1.yaml", team1)
        _write_yaml(tmpdir, "t2.yaml", team2)
        registry = TeamRegistry(config_dir=tmpdir)
        assert len(registry.all()) == 2
        assert registry.get("t1").name == "Team 1"
        assert registry.get("t2").asset_class == "crypto"


def test_real_quant_yaml():
    """Loads the actual data/teams/quant.yaml to verify it's valid."""
    registry = TeamRegistry("data/teams")
    config = registry.get("quant")
    assert config.team_id == "quant"
    assert len(config.agents) == 4
    assert len(config.schedule_cron) == 3
