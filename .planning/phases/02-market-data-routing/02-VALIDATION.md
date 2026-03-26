---
phase: 2
slug: market-data-routing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (installed in Phase 1) |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01 | 01 | 1 | DATA-04 | unit | `pytest tests/test_market_router.py -k router` | ❌ W0 | ⬜ pending |
| 02-02 | 01 | 1 | DATA-01 | integration | `pytest tests/test_market_router.py -k jupiter` | ❌ W0 | ⬜ pending |
| 02-03 | 01 | 1 | DATA-02 | integration | `pytest tests/test_market_router.py -k ccxt` | ❌ W0 | ⬜ pending |
| 02-04 | 01 | 1 | DATA-03 | integration | `pytest tests/test_market_router.py -k yfinance` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_market_router.py` — stubs for DATA-01 through DATA-04

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Jupiter returns real Solana prices | DATA-01 | Requires API key + network | Set JUP_API_KEY env var, run crypto team session, verify prices are non-zero |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
