"""Team configuration and registry — YAML-backed team definitions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger("quant_team")


@dataclass
class AgentSpec:
    """Specification for a single AI agent on a team."""
    name: str
    title: str
    system_prompt: str
    model: str = "claude-sonnet-4-20250514"


@dataclass
class RiskLimits:
    """Risk constraints for a team."""
    max_position_pct: float = 20.0
    max_exposure_pct: float = 80.0
    max_drawdown_pct: float = 20.0
    max_options_pct: float = 30.0


@dataclass
class TeamConfig:
    """Full configuration for a trading team."""
    team_id: str
    name: str
    asset_class: str
    agents: list[AgentSpec] = field(default_factory=list)
    risk_limits: RiskLimits = field(default_factory=RiskLimits)
    schedule_cron: list[dict] = field(default_factory=list)
    execution_backend: str = "paper"
    exchange: str = "binance"
    watchlist: list[str] = field(default_factory=list)


class TeamRegistry:
    """Loads and manages team configurations from YAML files."""

    def __init__(self, config_dir: str = "data/teams"):
        self._teams: dict[str, TeamConfig] = {}
        self._load_all(Path(config_dir))

    def _load_all(self, config_dir: Path) -> None:
        config_dir.mkdir(parents=True, exist_ok=True)
        for yaml_file in sorted(config_dir.glob("*.yaml")):
            try:
                config = self._load_file(yaml_file)
                self._teams[config.team_id] = config
                logger.info(f"Loaded team config: {config.team_id} ({config.name})")
            except Exception as e:
                raise ValueError(f"Failed to load team config {yaml_file}: {e}") from e

    def _load_file(self, path: Path) -> TeamConfig:
        with open(path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict in {path}, got {type(data).__name__}")
        return self._parse(data)

    def _parse(self, data: dict) -> TeamConfig:
        required = ["team_id", "name", "asset_class"]
        for key in required:
            if key not in data:
                raise ValueError(f"Missing required field: {key}")

        agents = [
            AgentSpec(
                name=a["name"],
                title=a["title"],
                system_prompt=a["system_prompt"],
                model=a.get("model", "claude-sonnet-4-20250514"),
            )
            for a in data.get("agents", [])
        ]

        risk_data = data.get("risk_limits", {})
        risk_limits = RiskLimits(
            max_position_pct=risk_data.get("max_position_pct", 20.0),
            max_exposure_pct=risk_data.get("max_exposure_pct", 80.0),
            max_drawdown_pct=risk_data.get("max_drawdown_pct", 20.0),
            max_options_pct=risk_data.get("max_options_pct", 30.0),
        )

        return TeamConfig(
            team_id=data["team_id"],
            name=data["name"],
            asset_class=data["asset_class"],
            agents=agents,
            risk_limits=risk_limits,
            schedule_cron=data.get("schedule_cron", []),
            execution_backend=data.get("execution_backend", "paper"),
            exchange=data.get("exchange", "binance"),
            watchlist=data.get("watchlist", []),
        )

    def get(self, team_id: str) -> TeamConfig:
        if team_id not in self._teams:
            raise KeyError(f"Unknown team: {team_id}. Available: {list(self._teams.keys())}")
        return self._teams[team_id]

    def all(self) -> list[TeamConfig]:
        return list(self._teams.values())
