"""Tests for the changed-files Python style gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_python_style.py"
SPEC = importlib.util.spec_from_file_location("check_python_style", MODULE_PATH)
assert SPEC is not None
check_python_style = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_python_style)


def test_filter_keeps_existing_python_files_only() -> None:
    files = check_python_style.filter_python_files(
        [
            "scripts/check_python_style.py",
            "README.md",
            "scripts/does_not_exist.py",
            "node_modules/pkg/tool.py",
            ".venv/lib/site.py",
            "scripts\\check_python_style.py",
        ]
    )
    assert files == ["scripts/check_python_style.py"]


def test_main_skips_when_nothing_changed(monkeypatch, capsys) -> None:
    monkeypatch.setattr(check_python_style, "changed_python_files", lambda base: [])
    assert check_python_style.main(["--base", "origin/main"]) == 0
    assert "No Python files" in capsys.readouterr().out


def test_flake8_blocks_unless_report_only(monkeypatch) -> None:
    monkeypatch.setattr(check_python_style, "changed_python_files", lambda base: ["a.py"])
    results = {"black --check": 0, "isort --check-only": 0, "flake8 (max-line-length 100)": 1}
    monkeypatch.setattr(check_python_style, "run_tool", lambda label, command: results[label])
    assert check_python_style.main([]) == 1
    assert check_python_style.main(["--report-only-flake8"]) == 0
    results["flake8 (max-line-length 100)"] = 0
    assert check_python_style.main([]) == 0
    results["black --check"] = 1
    assert check_python_style.main([]) == 1
