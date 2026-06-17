# Contributing to MarketHelm

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:

   ```bash
   git clone https://github.com/YOUR_USERNAME/market-helm.git
   cd market-helm
   ```

   **End users** can install from PyPI: `pip install market-helm` — see [PyPI](https://pypi.org/project/market-helm/) and the main README.

3. **Create a virtual environment**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

4. **Install in development mode**:

   ```bash
   pip install -e .
   pip install pytest pytest-cov  # For testing
   ```

## Package version (single source of truth)

The **canonical** release line for this repo is **`setup.cfg`** → **`[metadata]`** → **`version`** (e.g. `0.2.8`).

These must stay aligned for new contributors and CI:

- `dashboard/frontend/package.json` (`version`)
- `dashboard/frontend/package-lock.json` (root + `packages[""]` `version`)
- `dashboard/backend/main.py` (FastAPI `version=` and the root JSON `"version"` next to `"MarketHelm API"`)

**After you change `setup.cfg` version**, run:

```bash
python scripts/version_sync.py sync
```

**Check without writing:**

```bash
python scripts/version_sync.py check
```

The **CI** job runs **`check`** on every PR (read-only; it does **not** auto-fix so the PR stays an honest diff). **Publish to PyPI** sets `setup.cfg` from the **release tag** on the runner, then runs **`sync`** in the build job before **`npm ci`** so the wheel and UI metadata match that tag (still not committed to `main` from CI). After a successful release publish, **Post-release sync to main** (separate workflow) may open a PR to align `main` with that tag.

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Your Changes

- Follow the existing code structure
- Write clear, descriptive commit messages
- Add tests for new functionality
- Update documentation as needed

### 3. Run Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html

# Run specific test file
python -m pytest tests/core/test_config.py -v
```

### 4. Check Code Quality

```bash
# Format code (optional, but recommended)
pip install black isort
black src/ tests/
isort src/ tests/

# Lint code (optional)
pip install flake8
flake8 src/ tests/ --max-line-length=100
```

### 5. Commit Your Changes

```bash
git add .
git commit -m "feat: add new feature X"
# or
git commit -m "fix: resolve issue with Y"
```

**Commit Message Guidelines:**

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Adding or updating tests
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:

- Clear description of changes
- Reference to any related issues
- Screenshots (if UI changes)

## Code Structure

```text
src/
├── core/          # Core utilities (config, logging)
├── services/      # External data services (API, fetchers)
├── analysis/      # Data analysis & AI
├── storage/       # Data persistence
├── workflows/     # Business logic (reusable across interfaces)
└── cli/           # CLI interface (presentation layer)
```

**Key Principle**: Business logic in `workflows/` is reusable.
CLI/Web/API layers consume workflows for their specific presentation needs.

## Coding Standards

### Python Style

- Follow PEP 8
- Use type hints where appropriate
- Maximum line length: 100 characters
- Use descriptive variable names

### Imports

```python
# Standard library
import os
from pathlib import Path

# Third-party
import pandas as pd
import requests

# Local
from ..core.logger import setup_logger
from .api_client import FinnhubClient
```

### Documentation

- Add docstrings to all functions and classes
- Use Google-style docstrings:

```python
def function_name(param1: str, param2: int) -> bool:
    """
    Brief description of function.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When something goes wrong
    """
    pass
```

### Testing

- Write tests for new features
- Maintain or improve code coverage
- Use descriptive test names:

```python
def test_function_returns_expected_value_when_given_valid_input(self):
    """Test that function returns correct value with valid input."""
    # Arrange
    input_data = create_test_data()
    
    # Act
    result = function_under_test(input_data)
    
    # Assert
    self.assertEqual(result, expected_value)
```

## Areas for Contribution

**Roadmap detail:** See [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) for current status, what shipped, what’s next, and deferred items. **Hosting:** [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

### Current Gaps & Opportunities

- **Alerts (product):** Helmtower v1 shipped; remaining gaps are **reliability** (retry/backoff, delivery status UI) and **multi-user** (accounts, DB) — see [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md#product-requirements--alerts-non‑negotiable-direction).
- **Historical / accuracy:** Multi-day trends and **projection accuracy** (API + Historical Trends UI) are in place; deeper **metrics by confidence**, **risk-adjusted** views, and **business-calendar** target dates are still open.
- **Real-time:** Data is batch/daily; refresh is explicit (not streaming).
- **Screening:** Advanced technical filters (RSI/MACD, etc.) remain future work.

### Completed Milestones

- ✅ **Web Dashboard (v0.3+)** — Market overview, projections, Historical Trends, **projection accuracy**, **Helmtower** (`/alerts`).
- ✅ **Alerts** — `AlertEngine`, price/screening rules, cooldowns, **webhook** (JSON/Slack/Discord), **email** (SMTP + SendGrid/Mailgun), CLI, scheduled worker (`alerts run --loop`).

### Priority Features (ranked by impact)

#### Priority #1: Alert & notification system

**Status:** v1 shipped; **reliability + multi-user** next — [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md).

**On `main`:**

- [x] Alert engine (price threshold, screening match), storage, cooldowns
- [x] Log + **webhook** notifiers (JSON, Slack, Discord)
- [x] **SMTP email** + transactional providers (SendGrid, Mailgun)
- [x] CLI: `alerts init`, `alerts list`, `alerts test`, `alerts run --loop`
- [x] **Helmtower** — dashboard Settings UI for watches, email, webhooks, test send

**Next:**

- [ ] Email/webhook **retry/backoff**; optional delivery status in UI
- [ ] Later: accounts, DB, SMS/push

---

#### Priority #2: Historical trends & accuracy

**Status:** Partially implemented.

**Done / in repo:**

- [x] Multi-day aggregation, summary API, charts (confidence, recommendations, expected move)
- [x] Per-symbol historical chart with projection overlay
- [x] **Projection accuracy** — `GET /api/history/accuracy`, UI on Historical Trends

**Still to build:**

- [ ] Accuracy / trends **by confidence** band and richer performance metrics
- [ ] Recommendation change timeline, volume patterns (as needed)
- [ ] Optional business-day target alignment for scoring

---

#### Priority #3: Web dashboard enhancements

**Status:** Ongoing.

**Completed (examples):**

- [x] Dark mode, export, mobile-oriented layout (see dashboard README)
- [x] Projection accuracy views (Historical Trends)

**Still to build:**

- [ ] Code splitting / lazy routes, watchlist, shortcuts — see [dashboard/README.md](dashboard/README.md)

---

### High Priority - Additional Features

- [ ] **Support for additional stock exchanges** (international markets: LSE, TSE, HKEX)
- [ ] **More screening filters** (technical indicators: RSI, MACD, Bollinger Bands, moving averages)
- [ ] **Enhanced AI summaries** (sentiment analysis, news integration, contextual recommendations)
- [ ] **Sector analysis** (group stocks by sector, compare performance)
- [ ] **Portfolio tracking** (track multiple portfolios, performance metrics)
- [ ] **Backtesting engine** (test strategies against historical data)

### Medium Priority - Improvements

- [ ] Additional unit tests (especially for services/)
- [ ] Integration tests for full workflow
- [ ] Performance optimizations
- [ ] CLI improvements (progress bars, colors, interactive mode)

### Low Priority - Enhancements

- [ ] Configuration validation with detailed error messages
- [ ] Additional export formats (Excel, Parquet)
- [ ] Enhanced error handling and recovery

## Reporting Issues

When reporting issues, please include:

1. **Description**: Clear description of the issue
2. **Steps to Reproduce**: Minimal steps to reproduce the problem
3. **Expected Behavior**: What you expected to happen
4. **Actual Behavior**: What actually happened
5. **Environment**:
   - OS (Windows/Mac/Linux)
   - Python version
   - Relevant package versions
6. **Logs**: Relevant log excerpts from `logs/` directory

## Questions?

- Open an issue for general questions
- Check existing issues and PRs first
- Be respectful and constructive

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing!
