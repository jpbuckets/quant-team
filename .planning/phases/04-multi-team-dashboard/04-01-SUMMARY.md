---
phase: 04-multi-team-dashboard
plan: "01"
subsystem: api
tags: [team-scoped-api, portfolio, recommendations, sessions, multi-team]
dependency_graph:
  requires: []
  provides: [team-scoped-portfolio-api, cross-team-summary-api, team-detail-api]
  affects: [plan-02-dashboard-ui]
tech_stack:
  added: []
  patterns: [team_id-query-param, route-ordering-specificity]
key_files:
  created:
    - tests/test_dashboard_api.py
  modified:
    - quant_team/trading/portfolio_manager.py
    - quant_team/api/routers/portfolio.py
    - quant_team/api/routers/recommendations.py
    - quant_team/api/routers/sessions.py
    - quant_team/api/routers/teams.py
decisions:
  - /summary route placed before /{team_id} to avoid FastAPI treating "summary" as a team_id path param
  - team_id defaults to "quant" on portfolio endpoints for backward compat; optional (None) on recommendations/sessions to allow unfiltered queries
  - teams_summary uses try/except per-team so one failing team does not break the aggregate response
metrics:
  duration_seconds: 176
  completed_date: "2026-03-26"
  tasks_completed: 2
  files_modified: 5
---

# Phase 4 Plan 1: Team-Scoped API Endpoints Summary

**One-liner:** Team-scoped portfolio/recommendation/session API with backward-compatible `team_id` query params and a new cross-team aggregate summary endpoint.

## What Was Built

Added `team_id` filtering to all portfolio, recommendation, and session API endpoints. Added a `/api/teams/summary` cross-team aggregate endpoint and a `/api/teams/{team_id}` detail endpoint. All changes are backward compatible — existing callers without `team_id` continue to work via defaults.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| RED | Failing test suite for all 10 scenarios | 59073b5 | tests/test_dashboard_api.py |
| 1 | team_id filtering on PortfolioManager + all routers | e8519d5 | portfolio_manager.py, portfolio.py, recommendations.py, sessions.py |
| 2 | Cross-team summary and team detail endpoints | 08f3908 | teams.py |

## Endpoints Added / Modified

**Modified (team_id added):**
- `GET /api/portfolio?team_id=quant` — defaults to "quant", backward compat
- `GET /api/portfolio/history?team_id=quant`
- `GET /api/portfolio/trades?team_id=quant`
- `POST /api/portfolio/reset?team_id=quant`
- `POST /api/portfolio/snapshot?team_id=quant`
- `GET /api/recommendations?team_id=quant` — optional, unfiltered if absent
- `GET /api/recommendations/performance?team_id=quant`
- `GET /api/sessions?team_id=quant` — optional, unfiltered if absent
- `GET /api/sessions/latest?team_id=quant`

**New:**
- `GET /api/teams/summary` — aggregate across all teams with per-team breakdown
- `GET /api/teams/{team_id}` — full team detail with execution_backend and risk_limits

## PortfolioManager Changes

- `get_open_positions(team_id="quant")` — now filters by team
- `get_current_value(team_id="quant")` — delegates team_id to state and positions
- `take_snapshot(team_id="quant")` — sets snapshot.team_id
- `reset(team_id="quant")` — closes only the specified team's positions
- `check_stops(team_id="quant")` — delegates to get_open_positions

## Verification

- 10/10 dashboard API tests pass
- 73/73 existing tests pass, 1 skipped (no regressions)
- DB migrations applied: team_id column added to all 6 tables via `_maybe_add_team_id`

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written with one note: the DB migration (`_maybe_add_team_id` in connection.py) was already implemented in Phase 1 but the production DB had not been migrated yet. Running `init_db()` via the TestClient lifespan during test execution applied the migration automatically, which is the intended design.

## Known Stubs

None. All endpoints return real data from SQLite.

## Self-Check: PASSED
