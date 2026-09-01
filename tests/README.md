# MarketHelm — tests

## Overview

This directory contains unit tests for the MarketHelm project. The test layout mirrors the project structure so that each source module has a corresponding test package.

## Test Structure

Tests are organized to mirror the source code layout:

```text
tests/
├── __init__.py
├── conftest.py              # Pytest config: adds project root to sys.path
├── README.md
│
├── analysis/                # mirrors src/analysis/
│   ├── __init__.py
│   ├── test_ai_summarizer.py
│   ├── test_analyzer.py
│   └── test_projector.py
│
├── core/                    # mirrors src/core/
│   ├── __init__.py
│   ├── test_config.py
│   └── test_logger.py
│
├── services/                # mirrors src/services/
│   ├── __init__.py
│   └── test_api_client.py
│
├── storage/                 # mirrors src/storage/
│   ├── __init__.py
│   └── test_data_storage.py
│
├── workflows/               # mirrors src/workflows/
│   ├── __init__.py
│   └── test_tracker.py
│
├── alerts/                  # src/alerts/ notifiers + engine integration
│   └── test_webhook_notifier.py
│
└── dashboard/               # mirrors dashboard/
    ├── __init__.py
    └── backend/
        ├── __init__.py
        ├── api/
        │   ├── __init__.py
        │   └── test_api.py
        └── services/
            ├── __init__.py
            └── test_data_loader.py
```

## Path Setup

`conftest.py` adds the project root to `sys.path`, so tests can use:

- `from src.analysis.xxx import ...`
- `from dashboard.backend.services.xxx import ...`

No manual `sys.path.insert` is needed in individual test files.

## Running Tests

### Run All Tests

```bash
# Database-free suite from the project root
python -m pytest tests/ -v --ignore=tests/integration/test_postgresql_storage.py

# PostgreSQL integration against a disposable test database
MARKET_HELM_POSTGRES_TEST_URL=postgresql://user:password@localhost:5432/markethelm \
  python -m pytest tests/integration/test_postgresql_storage.py -v

# Or using unittest
python -m unittest discover tests/
```

### Run Specific Package

```bash
python -m pytest tests/analysis/
python -m pytest tests/core/
python -m pytest tests/dashboard/
```

### Run Specific Test File

```bash
python -m pytest tests/core/test_config.py -v
```

### Run Specific Test Class or Method

```bash
python -m pytest tests/core/test_config.py::TestCoreConfig
python -m pytest tests/core/test_config.py::TestCoreConfig::test_default_indices
```

### Run with Coverage

```bash
pip install pytest-cov
python -m pytest tests/ --ignore=tests/integration/test_postgresql_storage.py --cov=src --cov-report=html
```

## Test Coverage

| Module | Tests |
|--------|-------|
| `src/core/config.py` | Configuration loading and defaults |
| `src/core/logger.py` | Logging setup and handlers |
| `src/services/api_client.py` | Rate limiting and Finnhub API |
| `src/analysis/analyzer.py` | Stock data analysis |
| `src/analysis/ai_summarizer.py` | Demo summary, fallback when no API key |
| `src/analysis/projector.py` | Stock projections and recommendations |
| `src/storage/data_storage.py` | Data persistence |
| `src/workflows/tracker.py` | Workflow integration with mocked deps |
| `src/alerts/notifiers/webhook_notifier.py` | Webhook URL resolution, POST payload |
| `dashboard/backend/api` | Market, summary, health, history (incl. accuracy) |
| `dashboard/backend/services/data_loader.py` | Data loading, projection accuracy computation |

## Writing New Tests

1. **Mirror the source structure**  
   Place tests in the matching package:
   - `src/services/foo.py` → `tests/services/test_foo.py`

2. **Use descriptive names**  
   `test_` prefix, clear docstrings.

3. **Use `conftest.py` for shared setup**  
   Fixtures and path setup are centralized.

4. **Mock external dependencies**  
   Use `@patch` or `unittest.mock` for API calls and file I/O.

5. **Clean up resources**  
   Use `setUp`/`tearDown` or pytest fixtures for temp dirs.

## Dependencies

```bash
pip install pytest pytest-cov
```

## Next Priority

**Missing or light tests (by module):**

1. `src/services/data_fetcher.py` – Stock data fetching
2. `src/services/stock_screener.py` – Screening logic
3. `src/services/index_fetcher.py` – Index constituent fetching
4. `src/alerts/alert_engine.py`, `alert_rules.py`, `alert_storage.py` – Beyond webhook notifier coverage
5. Integration tests for full workflow (end-to-end with temp `data/`)

**Roadmap:** [docs/PROJECT_STATUS.md](../docs/PROJECT_STATUS.md)
