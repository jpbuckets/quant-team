# Testing

## Current State

**No testing infrastructure exists in this project.**

- No test framework configured (no pytest.ini, conftest.py, or test directories)
- No test files in the project source code
- No CI/CD pipeline for automated testing
- No requirements-dev.txt or test dependencies

## Test Coverage

**Coverage: 0%** — No tests exist.

## Recommendations

### Framework
- **pytest** — Standard for Python projects, well-suited for testing async code and web applications
- Add to requirements: `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx` (for testing FastAPI/Starlette)

### Structure
```
tests/
  conftest.py          # Shared fixtures
  test_analysis.py     # Analysis engine tests
  test_api.py          # API endpoint tests
  test_strategies.py   # Trading strategy tests
```

### Priority Areas
1. **Analysis engine** — Core business logic, highest value for testing
2. **API endpoints** — Integration tests for web interface
3. **Data processing** — Ensure market data is handled correctly
4. **Strategy calculations** — Verify trading signal accuracy

---
*Mapped: 2026-03-25*
