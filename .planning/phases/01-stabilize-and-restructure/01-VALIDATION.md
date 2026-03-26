---
phase: 1
slug: stabilize-and-restructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (to be installed in Wave 0) |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01 | 01 | 1 | STAB-01 | integration | `pytest tests/test_analysis.py -k timeout` | ❌ W0 | ⬜ pending |
| 01-02 | 01 | 1 | STAB-02 | integration | `pytest tests/test_analysis.py -k concurrent` | ❌ W0 | ⬜ pending |
| 01-03 | 01 | 1 | STAB-03 | unit | `pytest tests/test_auth.py` | ❌ W0 | ⬜ pending |
| 01-04 | 01 | 1 | STAB-04 | integration | `pytest tests/test_analysis.py -k progress` | ❌ W0 | ⬜ pending |
| 01-05 | 02 | 2 | TEAM-01 | unit | `pytest tests/test_teams.py -k registry` | ❌ W0 | ⬜ pending |
| 01-06 | 02 | 2 | TEAM-02 | unit | `pytest tests/test_teams.py -k scoping` | ❌ W0 | ⬜ pending |
| 01-07 | 02 | 2 | TEAM-03 | unit | `pytest tests/test_teams.py -k orchestrator` | ❌ W0 | ⬜ pending |
| 01-08 | 02 | 2 | TEAM-04 | unit | `pytest tests/test_teams.py -k agents` | ❌ W0 | ⬜ pending |
| 01-09 | 02 | 2 | TEAM-05 | unit | `pytest tests/test_teams.py -k schedule` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pytest>=7.0.0` and `pytest-asyncio>=0.23.0` added to dev dependencies
- [ ] `tests/conftest.py` — shared fixtures (test DB, mock Anthropic client)
- [ ] `tests/test_analysis.py` — stubs for STAB-01, STAB-02, STAB-04
- [ ] `tests/test_auth.py` — stubs for STAB-03
- [ ] `tests/test_teams.py` — stubs for TEAM-01 through TEAM-05

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Progress indicator visible in UI | STAB-04 | Requires browser interaction | Start analysis, observe progress bar/indicator updates in real-time |
| YAML team config loads new team | TEAM-01 | Requires file system + app restart | Create new YAML team config, restart app, verify team appears |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
