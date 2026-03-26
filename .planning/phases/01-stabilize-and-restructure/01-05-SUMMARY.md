---
phase: 01-stabilize-and-restructure
plan: 05
subsystem: team-registry
tags: [team-config, yaml, orchestrator, multi-team, scheduler]
dependency_graph:
  requires: ["01-02", "01-04"]
  provides: ["TeamRegistry", "TeamOrchestrator", "quant.yaml", "per-team-scheduling"]
  affects: ["quant_team/orchestrator.py", "quant_team/api/app.py", "quant_team/api/routers/recommendations.py"]
tech_stack:
  added: ["pyyaml (yaml.safe_load)"]
  patterns: ["YAML-backed config registry", "dynamic agent construction from config", "per-team cron scheduling"]
key_files:
  created:
    - quant_team/teams/__init__.py
    - quant_team/teams/registry.py
    - data/teams/quant.yaml
  modified:
    - quant_team/orchestrator.py
    - quant_team/api/app.py
    - quant_team/api/routers/recommendations.py
    - tests/test_registry.py
    - tests/test_orchestrator.py
    - .gitignore
decisions:
  - "TradingDesk alias retained for backward compatibility while renaming to TeamOrchestrator"
  - "data/ gitignore changed from whole-directory to specific exclusions to allow data/teams/ YAML tracking"
  - "Dynamic agent loop: all agents except last = analysts, last = decision-maker (CIO pattern preserved without hardcoding)"
  - "AgentSession macro/quant/risk fields populated by agent name.lower() lookup with fallback to original key names"
metrics:
  duration_seconds: 901
  completed_date: "2026-03-26"
  tasks_completed: 2
  files_changed: 9
---

# Phase 01 Plan 05: YAML TeamRegistry and TeamOrchestrator Summary

**One-liner:** YAML-backed TeamRegistry with TeamConfig/AgentSpec dataclasses replacing hardcoded agent imports in orchestrator — adding a new team now requires only a YAML file drop.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create TeamConfig/AgentSpec/TeamRegistry and quant.yaml | 6a98786 | quant_team/teams/__init__.py, quant_team/teams/registry.py, data/teams/quant.yaml, .gitignore |
| 2 | Refactor orchestrator to TeamOrchestrator and wire into app | edfb5d4 | quant_team/orchestrator.py, quant_team/api/app.py, quant_team/api/routers/recommendations.py, tests/test_registry.py, tests/test_orchestrator.py |

## What Was Built

### TeamRegistry (`quant_team/teams/registry.py`)
- `AgentSpec` dataclass: name, title, system_prompt, model
- `RiskLimits` dataclass: max_position_pct, max_exposure_pct, max_drawdown_pct, max_options_pct
- `TeamConfig` dataclass: team_id, name, asset_class, agents, risk_limits, schedule_cron, execution_backend, watchlist
- `TeamRegistry` class: loads all `*.yaml` files from `data/teams/` at startup, raises `ValueError` on malformed configs

### quant.yaml (`data/teams/quant.yaml`)
- team_id: quant, asset_class: stocks
- 9-ticker watchlist (AAPL, MSFT, NVDA, GOOGL, AMZN, TSLA, META, SPY, QQQ)
- 3 schedule entries (9:35, 12:00, 15:30)
- Risk limits matching original hardcoded values
- 4 agents with full system prompts extracted verbatim from Python agent modules (Macro, Quant, Risk, CIO)

### TeamOrchestrator (`quant_team/orchestrator.py`)
- Renamed from `TradingDesk`; `TradingDesk = TeamOrchestrator` alias retained for backward compatibility
- `__init__` accepts `TeamConfig` instead of no config; constructs `Agent` instances dynamically from `config.agents`
- No hardcoded imports of individual agent modules (`from .agents import cio` etc. removed)
- Dynamic agent loop: all agents[:-1] are analysts, agents[-1] is decision-maker
- `AgentSession` and `Recommendation` records include `team_id=self.config.team_id`

### App wiring
- `_setup_scheduler`: iterates `TeamRegistry().all()` to schedule per-team cron jobs
- `_run_scheduled_session`: accepts `team_id` parameter, loads config from registry
- `recommendations.py _run_session`: uses `TeamRegistry + TeamOrchestrator` instead of `TradingDesk`

## Test Results

```
27 passed, 1 skipped
```

- `test_registry.py`: 6 tests — load valid YAML, invalid YAML raises, missing required field raises, schedule_cron populated, multiple teams loaded, real quant.yaml valid
- `test_orchestrator.py`: 3 tests — dynamic agent construction, system_prompt from config, no hardcoded imports; 1 intentional skip (integration test deferred)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] .gitignore prevented tracking data/teams/ YAML configs**
- **Found during:** Task 1 commit
- **Issue:** `.gitignore` had `data/` as a blanket ignore, blocking `data/teams/quant.yaml` from being committed. YAML configs are required for the app to function and must be tracked.
- **Fix:** Changed `.gitignore` from ignoring `data/` wholesale to ignoring only specific runtime files (`data/*.db`, `data/sessions/`, `data/ips_log.json`, `data/wallet.json`, `data/ips.md`)
- **Files modified:** `.gitignore`
- **Commit:** 6a98786

## Known Stubs

None. All 4 agent system prompts are fully wired from quant.yaml into TeamOrchestrator. The `TeamRegistry().get("quant")` call in `recommendations.py` and `app.py` hardcodes `"quant"` as the team — this is intentional for Phase 1 and will be resolved when multi-team routing is implemented in a future plan.

## Self-Check: PASSED

- quant_team/teams/__init__.py: FOUND
- quant_team/teams/registry.py: FOUND
- data/teams/quant.yaml: FOUND
- quant_team/orchestrator.py contains TeamOrchestrator: FOUND
- quant_team/orchestrator.py TradingDesk alias: FOUND
- Commits 6a98786, edfb5d4: FOUND
- All 27 tests pass: VERIFIED
