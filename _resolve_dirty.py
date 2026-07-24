"""Re-resolve DIRTY test PRs against latest main: main prod + unique tests (+ known prod ports)."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, encoding="utf-8", capture_output=True, check=check)


def show(spec: str) -> str:
    return subprocess.check_output(["git", "show", spec], text=True, encoding="utf-8")


def defs(text: str) -> set[str]:
    return set(re.findall(r"^\s*def (test_\w+)", text, re.M))


def extract(text: str, name: str) -> str | None:
    lines = text.splitlines(True)
    start = None
    indent = None
    idx = 0
    for idx, line in enumerate(lines):
        if re.match(rf"[ \t]*def {name}\(", line):
            j = idx
            while j > 0 and lines[j - 1].lstrip().startswith("@"):
                j -= 1
            start = j
            indent = len(line) - len(line.lstrip())
            break
    if start is None:
        return None
    end = len(lines)
    for k in range(idx + 1, len(lines)):
        line = lines[k]
        if not line.strip():
            continue
        cur = len(line) - len(line.lstrip())
        if cur <= indent and (
            line.lstrip().startswith("def ")
            or line.lstrip().startswith("class ")
            or line.lstrip().startswith("@")
        ):
            end = k
            break
    return "".join(lines[start:end]).rstrip()


def write_tests_from_stages_or_refs(path: str, pr_ref: str) -> list[str]:
    try:
        ours = subprocess.check_output(["git", "show", f":2:{path}"], text=True, encoding="utf-8")
        theirs = subprocess.check_output(["git", "show", f":3:{path}"], text=True, encoding="utf-8")
    except subprocess.CalledProcessError:
        ours = show(f"{pr_ref}:{path}")
        theirs = show(f"origin/main:{path}")
    unique = sorted(defs(ours) - defs(theirs))
    pieces = [p for n in unique if (p := extract(ours, n))]
    Path(path).write_text(
        theirs.rstrip() + ("\n\n" + "\n\n".join(pieces) + "\n" if pieces else "\n"),
        encoding="utf-8",
    )
    print(path, "unique", unique)
    return unique


def ensure_movers_empty_guard(market: str) -> str:
    marker = 'async def get_top_movers'
    if marker not in market:
        return market
    block_start = market.find(marker)
    block = market[block_start:block_start + 1200]
    guard = (
        '        if df is None or getattr(df, "empty", False) or "change_percent" not in df.columns:\n'
        '            raise HTTPException(status_code=404, detail="No data available.")\n'
    )
    if guard in block:
        return market
    old = (
        "        df = loader.load_daily_data()\n"
        "        \n"
        "        # Filter by sign first so a large limit"
    )
    new = (
        "        df = loader.load_daily_data()\n"
        + guard
        + "\n"
        "        # Filter by sign first so a large limit"
    )
    if old not in market:
        old = (
            "        df = loader.load_daily_data()\n"
            "\n"
            "        # Filter by sign first so a large limit"
        )
        new = (
            "        df = loader.load_daily_data()\n"
            + guard
            + "\n"
            "        # Filter by sign first so a large limit"
        )
    if old not in market:
        raise SystemExit("movers empty insert missing")
    return market.replace(old, new, 1)


def ensure_movers_finite_loop(market: str) -> str:
    if "_safe_volume(row.get('volume'" in market.split("async def get_top_movers", 1)[-1][:2000]:
        return market
    if "def _finite_float" not in market:
        raise SystemExit("need _finite_float helper on market before loop port")
    old = """        movers = []
        for _, row in sorted_df.iterrows():
            movers.append(StockMover(
                symbol=row['symbol'],
                name=row.get('name', row['symbol']),
                price=float(row['close']),
                change=float(row['change']),
                changePercent=float(row['change_percent']),
                volume=int(row.get('volume', 0))
            ))"""
    new = """        movers = []
        for _, row in sorted_df.iterrows():
            # Skip non-finite price fields so one corrupt CSV row cannot null the payload
            # or abort the whole movers card via int(float('nan')).
            price = _finite_float(row.get('close'))
            change = _finite_float(row.get('change'))
            change_percent = _finite_float(row.get('change_percent'))
            if price is None or change is None or change_percent is None:
                continue
            movers.append(StockMover(
                symbol=row['symbol'],
                name=row.get('name', row['symbol']),
                price=price,
                change=change,
                changePercent=change_percent,
                volume=_safe_volume(row.get('volume', 0)),
            ))"""
    if old not in market:
        # already partially updated
        if "price = _finite_float" in market:
            return market
        raise SystemExit("movers loop not found")
    return market.replace(old, new, 1)


def resolve_generic(branch: str, prod_take_main: list[str], test_paths: list[str]) -> None:
    run(["git", "fetch", "origin", "main", branch])
    run(["git", "checkout", "-B", branch, f"origin/{branch}"])
    merge = run(
        ["git", "merge", "origin/main", "-m", f"Merge branch 'main' into {branch}"],
        check=False,
    )
    print(merge.stdout)
    print(merge.stderr)
    if merge.returncode == 0:
        print("clean merge")
        return
    conflicts = run(["git", "diff", "--name-only", "--diff-filter=U"], check=False).stdout.strip().splitlines()
    conflicts = [c for c in conflicts if c]
    print("conflicts", conflicts)
    pr_ref = f"origin/{branch}"
    for path in conflicts:
        if path.startswith("tests/") or "/test_" in path:
            write_tests_from_stages_or_refs(path, pr_ref)
        elif path in prod_take_main or path.endswith(".py"):
            # default: main, then optional ports below
            Path(path).write_text(show(f"origin/main:{path}"), encoding="utf-8")
            print("took main", path)
        else:
            Path(path).write_text(show(f"origin/main:{path}"), encoding="utf-8")
            print("took main", path)
    # ensure test paths written even if not conflicted? skip
    for path in test_paths:
        if path in conflicts:
            continue
        # still fine
    run(["git", "add", "-A"])


def main() -> None:
    which = sys.argv[1]
    if which == "272":
        branch = "cursor/test-coverage-automation-9d96"
        resolve_generic(
            branch,
            ["dashboard/backend/api/market.py", "dashboard/backend/api/projections.py"],
            ["tests/dashboard/backend/api/test_api.py"],
        )
        # re-port #272 guards onto main market/projections
        market = Path("dashboard/backend/api/market.py").read_text(encoding="utf-8")
        market = ensure_movers_empty_guard(market)
        # keep finite loop if main already has from #278
        Path("dashboard/backend/api/market.py").write_text(market, encoding="utf-8")
        # projections: ensure _safe_float means + recommendation guard if missing
        proj = Path("dashboard/backend/api/projections.py").read_text(encoding="utf-8")
        pr = show(f"origin/{branch}:dashboard/backend/api/projections.py")
        if "_safe_float(df['confidence'].mean())" not in proj and "def _safe_float" in proj:
            proj = re.sub(
                r"avg_confidence = float\(df\['confidence'\]\.mean\(\)\) if 'confidence' in df\.columns else 0",
                "avg_confidence = (\n"
                "            _safe_float(df['confidence'].mean()) if 'confidence' in df.columns else 0.0\n"
                "        )",
                proj,
            )
            proj = re.sub(
                r"avg_expected_change = float\(df\['expected_change_percent'\]\.mean\(\)\) if 'expected_change_percent' in df\.columns else 0",
                "avg_expected_change = (\n"
                "            _safe_float(df['expected_change_percent'].mean())\n"
                "            if 'expected_change_percent' in df.columns\n"
                "            else 0.0\n"
                "        )",
                proj,
            )
        if 'or "recommendation" not in proj_df.columns' not in proj:
            # try port from PR
            if 'or "recommendation" not in proj_df.columns' in pr:
                guard_m = re.search(
                    r"        # Missing ranking columns.*?\n        # Map type to recommendation string",
                    pr,
                    re.S,
                )
                if guard_m and "# Map type to recommendation string" in proj:
                    proj = proj.replace(
                        "        # Map type to recommendation string",
                        guard_m.group(0).rsplit("# Map type", 1)[0] + "# Map type to recommendation string",
                        1,
                    )
        Path("dashboard/backend/api/projections.py").write_text(proj, encoding="utf-8")
        run(["git", "add", "-A"])
        print("272 ports applied")
    elif which == "270":
        resolve_generic(
            "cursor/test-coverage-automation-f52e",
            [],
            [
                "tests/alerts/test_alert_engine.py",
                "tests/workflows/test_tracker.py",
            ],
        )
    elif which == "266":
        resolve_generic(
            "cursor/test-coverage-automation-e6ff",
            [],
            [
                "tests/alerts/test_alert_paths.py",
                "tests/dashboard/backend/api/test_alerts_api.py",
            ],
        )
    else:
        raise SystemExit("272|270|266")


if __name__ == "__main__":
    main()
