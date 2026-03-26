"""Tests for TeamRegistry and YAML config loading (TEAM-01, TEAM-05)."""
from __future__ import annotations

import pytest


def test_load_yaml_config(sample_team_config_dict):
    """TeamRegistry loads a valid YAML file and returns TeamConfig."""
    pytest.skip("TEAM-01: Implement after TeamRegistry created")


def test_invalid_yaml_raises():
    """TeamRegistry raises clear error for invalid/malformed YAML."""
    pytest.skip("TEAM-01: Implement after TeamRegistry created")


def test_schedule_cron_from_yaml(sample_team_config_dict):
    """TeamConfig.schedule_cron is populated from YAML schedule field."""
    pytest.skip("TEAM-05: Implement after TeamConfig has schedule_cron")


def test_multiple_teams_loaded():
    """TeamRegistry loads multiple YAML files from directory."""
    pytest.skip("TEAM-01: Implement after TeamRegistry created")
