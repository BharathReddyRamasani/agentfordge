"""Frontend build harness: installs and builds the generated React + Vite application
in a sandboxed subprocess with timeouts. Feeds the engineering build->fix->rebuild loop."""

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.tools.terminal import run_command, sandbox_env


class BuildCancelled(Exception):
    """Raised when cancellation is requested between build sub-stages."""


@dataclass
class BuildResult:
    ok: bool
    stage: str
    output: str
    dist_path: str


def _npm() -> str | None:
    resolved = shutil.which("npm") or shutil.which("npm.cmd")
    return resolved


def node_available() -> bool:
    return _npm() is not None


def build_frontend(
    app_root: str | Path,
    on_phase: Callable[[dict], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> BuildResult:
    """npm install (if needed) + vite build for the generated app frontend.

    on_phase receives {"phase": "npm_install"|"vite_build", "event": "started"|"finished",
    "ok": bool, "duration_s": float} so orchestrators can stream sub-stage progress.
    should_cancel is polled between sub-stages; on True, BuildCancelled is raised.
    """
    fe = Path(app_root) / "frontend"
    dist = fe / "dist"
    npm = _npm()
    if npm is None:
        return BuildResult(False, "frontend_build", "Node.js/npm is not available on this host; the generated React frontend cannot be built", "")
    if not (fe / "package.json").exists():
        return BuildResult(False, "frontend_build", "frontend/package.json is missing", "")

    def cancelled() -> bool:
        try:
            return bool(should_cancel and should_cancel())
        except Exception:
            return False

    logs: list[str] = []
    if not (fe / "node_modules").exists():
        if on_phase:
            on_phase({"phase": "npm_install", "event": "started"})
        install = run_command(
            [npm, "install", "--no-audit", "--no-fund", "--loglevel", "error"],
            cwd=str(fe),
            timeout=max(settings.sandbox_timeout, 600),
            env=sandbox_env(),
        )
        if on_phase:
            on_phase({"phase": "npm_install", "event": "finished", "ok": install.ok, "duration_s": install.duration_s})
        logs.append(f"$ npm install -> exit {install.returncode} ({install.duration_s}s)")
        if install.stdout:
            logs.append(install.stdout[-3000:])
        if install.stderr:
            logs.append(install.stderr[-2000:])
        if not install.ok:
            return BuildResult(False, "frontend_build", "\n".join(logs), "")
    else:
        logs.append("$ npm install skipped (node_modules present)")

    if cancelled():
        raise BuildCancelled("cancel requested between install and build")

    if on_phase:
        on_phase({"phase": "vite_build", "event": "started"})
    build = run_command(
        [npm, "run", "build", "--loglevel", "error"],
        cwd=str(fe),
        timeout=max(settings.sandbox_timeout, 300),
        env=sandbox_env(),
    )
    if on_phase:
        on_phase({"phase": "vite_build", "event": "finished", "ok": build.returncode == 0, "duration_s": build.duration_s})
    logs.append(f"$ npm run build -> exit {build.returncode} ({build.duration_s}s)")
    if build.stdout:
        logs.append(build.stdout[-3000:])
    if build.stderr:
        logs.append(build.stderr[-2000:])

    ok = (dist / "index.html").exists()
    logs.append(f"dist/index.html {'present' if ok else 'MISSING'}")
    return BuildResult(ok, "frontend_build", "\n".join(logs), str(dist))
