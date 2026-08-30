"""Dockerfile.web must copy the Vite build from the configured outDir.

The web image used to COPY --from=frontend /build/dist, Vite's default emit
path. dashboard/frontend/vite.config.ts writes to ../backend/static, which
resolves to /backend/static against the frontend stage WORKDIR /build. A
successful npm run build then left the Python image without index.html, so
the hosted SPA never mounted.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "Dockerfile.web"
VITE_CONFIG = REPO_ROOT / "dashboard" / "frontend" / "vite.config.ts"
BACKEND_MAIN = REPO_ROOT / "dashboard" / "backend" / "main.py"


def _frontend_stage(dockerfile: str) -> str:
    stages = re.split(r"^FROM\s+", dockerfile, flags=re.MULTILINE)
    for stage in stages:
        if "AS frontend" in stage or " as frontend" in stage:
            return stage
    raise AssertionError("Dockerfile.web has no frontend stage")


def _frontend_workdir(dockerfile: str) -> str:
    stage = _frontend_stage(dockerfile)
    match = re.search(r"^WORKDIR\s+(\S+)", stage, re.MULTILINE)
    if match is None:
        raise AssertionError("frontend stage has no WORKDIR")
    return match.group(1)


def _vite_outdir(vite_config: str) -> str:
    match = re.search(r"outDir:\s*['\"]([^'\"]+)['\"]", vite_config)
    if match is None:
        raise AssertionError("vite.config.ts has no string outDir")
    return match.group(1)


def _copy_from_frontend(dockerfile: str) -> tuple[str, str]:
    match = re.search(
        r"^COPY --from=frontend\s+(\S+)\s+(\S+)\s*$",
        dockerfile,
        re.MULTILINE,
    )
    if match is None:
        raise AssertionError("Dockerfile.web has no COPY --from=frontend")
    return match.group(1), match.group(2)


def test_dockerfile_web_copies_vite_outdir_into_fastapi_static() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    vite_config = VITE_CONFIG.read_text(encoding="utf-8")
    backend_main = BACKEND_MAIN.read_text(encoding="utf-8")

    workdir = _frontend_workdir(dockerfile)
    outdir = _vite_outdir(vite_config)
    copy_src, copy_dest = _copy_from_frontend(dockerfile)
    resolved_src = posixpath.normpath(posixpath.join(workdir, outdir))

    assert copy_src == resolved_src, (
        f"COPY --from=frontend source {copy_src!r} does not match "
        f"WORKDIR {workdir!r} + Vite outDir {outdir!r} = {resolved_src!r}"
    )
    assert copy_dest in {
        "./dashboard/backend/static",
        "dashboard/backend/static",
    }
    assert (
        '_STATIC_DIR = Path(__file__).resolve().parent / "static"'
        in backend_main
    )
