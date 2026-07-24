"""Resolve conflicted test-coverage PRs by merging main and porting PR prod+tests."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True, encoding="utf-8")


def show(spec: str) -> str:
    return run(["git", "show", spec])


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


def write_tests(main_path: str, pr_ref: str, dest: str) -> list[str]:
    ours = show(f"{pr_ref}:{main_path}")
    theirs = show(f"origin/main:{main_path}")
    unique = sorted(defs(ours) - defs(theirs))
    pieces = [p for n in unique if (p := extract(ours, n))]
    Path(dest).write_text(
        theirs.rstrip() + ("\n\n" + "\n\n".join(pieces) + "\n" if pieces else "\n"),
        encoding="utf-8",
    )
    return unique


def port_278_market() -> None:
    main = show("origin/main:dashboard/backend/api/market.py")
    if "def _finite_float" not in main:
        helper = '''

def _finite_float(value: Any) -> Optional[float]:
    """Return float when finite; otherwise None (missing/non-numeric/NaN/Inf)."""
    try:
        if value is None:
            return None
        result = float(value)
        if not math.isfinite(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _safe_volume(value: Any) -> int:
    """Coerce volume to a finite int; bad/missing cells become 0 (never abort the list)."""
    try:
        if value is None:
            return 0
        result = float(value)
        if not math.isfinite(result):
            return 0
        return int(result)
    except (TypeError, ValueError):
        return 0


'''
        # ensure Optional imported
        if "Optional" not in main.split("from typing import", 1)[-1].split("\n", 1)[0]:
            main = main.replace(
                "from typing import Any, Dict, Optional",
                "from typing import Any, Dict, Optional",
            )
            if "from typing import" in main and "Optional" not in main[
                main.find("from typing import") : main.find("from typing import") + 80
            ]:
                main = re.sub(
                    r"from typing import ([^\n]+)",
                    lambda m: (
                        m.group(0)
                        if "Optional" in m.group(1)
                        else f"from typing import {m.group(1)}, Optional"
                    ),
                    main,
                    count=1,
                )
        if "import math" not in main:
            main = "import math\n" + main
        anchor = "def _generate_demo_summary"
        if "def _safe_float" in main:
            # insert after _safe_float block end (before _generate_demo_summary)
            idx = main.find(anchor)
            main = main[:idx] + helper.lstrip("\n") + main[idx:]
        else:
            main = main.replace("router = APIRouter()\n", "router = APIRouter()\n" + helper, 1)
        print("278 market: helpers")

    old_loop = """        movers = []
        for _, row in sorted_df.iterrows():
            movers.append(StockMover(
                symbol=row['symbol'],
                name=row.get('name', row['symbol']),
                price=float(row['close']),
                change=float(row['change']),
                changePercent=float(row['change_percent']),
                volume=int(row.get('volume', 0))
            ))"""
    new_loop = """        movers = []
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
    if old_loop in main:
        main = main.replace(old_loop, new_loop, 1)
        print("278 market: movers loop")
    elif "_safe_volume(row.get('volume'" in main:
        print("278 market: movers loop already present")
    else:
        raise SystemExit("278 market movers loop not found")
    Path("dashboard/backend/api/market.py").write_text(main, encoding="utf-8")


def port_278_projections() -> None:
    # Prefer PR file for projections helpers+opportunities row coercion, but keep main's
    # summary _safe_float / opportunities column guards if present.
    main = show("origin/main:dashboard/backend/api/projections.py")
    pr = show("origin/cursor/test-coverage-automation-362e:dashboard/backend/api/projections.py")

    # Start from whichever is newer/longer with both feature sets: take main then port PR helpers+row loop
    if "def _finite_float" not in main:
        # insert helpers after router / existing _safe_float
        helper = '''

def _finite_float(value: Any) -> Optional[float]:
    """Return float when finite; otherwise None (missing/non-numeric/NaN/Inf)."""
    try:
        if value is None:
            return None
        result = float(value)
        if not math.isfinite(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _safe_volume(value: Any) -> int:
    """Coerce volume to a finite int; bad/missing cells become 0 (never abort the list)."""
    try:
        if value is None:
            return 0
        result = float(value)
        if not math.isfinite(result):
            return 0
        return int(result)
    except (TypeError, ValueError):
        return 0


'''
        if "import math" not in main:
            main = main.replace(
                '"""\nProjections API endpoints\n"""\n',
                '"""\nProjections API endpoints\n"""\nimport math\nfrom typing import Any, Optional\n',
                1,
            )
        elif "Optional" not in main:
            main = main.replace("from typing import Any\n", "from typing import Any, Optional\n", 1)
        # place after _safe_float if present else after router
        if "def _safe_float" in main:
            m = re.search(r"def _safe_float.*?(?=\n@router|\nasync def |\nDef )", main, re.S)
            if not m:
                raise SystemExit("cannot find _safe_float end")
            insert_at = m.end()
            main = main[:insert_at] + "\n" + helper + main[insert_at:]
        else:
            main = main.replace("router = APIRouter()\n\n\n", "router = APIRouter()\n" + helper, 1)
        print("278 proj: helpers")

    # Port opportunities row building from PR if main still uses raw float/int
    if "volume=_safe_volume" not in main and "_safe_volume(" not in main.split("async def get_opportunities")[-1]:
        # extract opportunities loop from PR
        pr_opp = pr.split("async def get_opportunities", 1)[1]
        main_opp_head = main.split("async def get_opportunities", 1)[0]
        # find old append pattern in main
        old = None
        for candidate in re.finditer(
            r"        opportunities = \[\]\n        for .*?return OpportunitiesResponse",
            main.split("async def get_opportunities", 1)[1],
            re.S,
        ):
            old = candidate.group(0)
            break
        new_m = re.search(
            r"        opportunities = \[\]\n        for .*?return OpportunitiesResponse",
            pr_opp,
            re.S,
        )
        if not old or not new_m:
            raise SystemExit("opportunities loop not found")
        main = main.replace(old, new_m.group(0), 1)
        print("278 proj: opportunities loop")
    else:
        print("278 proj: opportunities loop already ok")

    Path("dashboard/backend/api/projections.py").write_text(main, encoding="utf-8")


def port_287() -> None:
    # For analyzer/projector/alert_jobs: take PR versions merged conceptually onto main
    # by using PR file when it's a pure hardening of the same functions.
    for rel in (
        "src/analysis/analyzer.py",
        "src/analysis/projector.py",
        "src/storage/alert_jobs.py",
    ):
        main = show(f"origin/main:{rel}")
        pr = show(f"origin/cursor/test-coverage-automation-fff7:{rel}")
        # If main already contains the key PR markers, keep main; else take PR content
        markers = {
            "src/analysis/analyzer.py": "def _finite_mask",
            "src/analysis/projector.py": "def _finite_mean",
            "src/storage/alert_jobs.py": "Corrupt payload_json",
        }
        marker = markers[rel]
        if marker in main:
            Path(rel).write_text(main, encoding="utf-8")
            print(rel, "already on main")
        else:
            # Prefer applying PR file directly only if base is close — use PR
            Path(rel).write_text(pr, encoding="utf-8")
            print(rel, "took PR version")


def resolve(pr_number: int, branch: str, kind: str) -> None:
    run(["git", "fetch", "origin", "main", branch])
    subprocess.check_call(["git", "checkout", "-B", branch, f"origin/{branch}"])
    merge = subprocess.run(
        ["git", "merge", "origin/main", "-m", f"Merge branch 'main' into {branch}"],
        text=True,
        capture_output=True,
    )
    print(merge.stdout)
    print(merge.stderr)
    conflicts = run(["git", "diff", "--name-only", "--diff-filter=U"]).strip().splitlines()
    conflicts = [c for c in conflicts if c]
    print("conflicts", conflicts)
    if kind == "278":
        port_278_market()
        port_278_projections()
        unique = write_tests(
            "tests/dashboard/backend/api/test_api.py",
            f"origin/{branch}",
            "tests/dashboard/backend/api/test_api.py",
        )
        print("unique tests", unique)
    elif kind == "287":
        port_287()
        for rel in (
            "tests/analysis/test_analyzer.py",
            "tests/analysis/test_projector.py",
            "tests/storage/test_alert_jobs.py",
        ):
            if rel in conflicts or True:
                unique = write_tests(rel, f"origin/{branch}", rel)
                print(rel, "unique", unique)
    else:
        raise SystemExit(kind)
    subprocess.check_call(["git", "add", "-A"])
    print("resolved files staged")


if __name__ == "__main__":
    kind = sys.argv[1]
    if kind == "278":
        resolve(278, "cursor/test-coverage-automation-362e", "278")
    elif kind == "287":
        resolve(287, "cursor/test-coverage-automation-fff7", "287")
    else:
        raise SystemExit("usage: 278|287")
