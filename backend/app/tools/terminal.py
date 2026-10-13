"""Terminal tool: controlled command execution with timeout and command restrictions."""

import os
import subprocess
from dataclasses import dataclass

MAX_OUTPUT_CHARS = 60000

BLOCKED_PATTERNS = (
    "rm -rf /",
    "format c:",
    "del /f /s /q c:\\",
    "shutdown",
    "rmdir /s /q c:\\",
)


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


def sandbox_env(extra: dict | None = None) -> dict:
    """Build a restricted environment for untrusted/generated code execution.

    Secrets (LLM/API keys, JWT secret) are never passed to generated processes.
    """
    keep = {"SYSTEMROOT", "TEMP", "TMP", "PATH", "COMSPEC", "PATHEXT", "APPDATA", "LOCALAPPDATA", "HOME", "USERPROFILE"}
    env = {k: v for k, v in os.environ.items() if k in keep}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra:
        env.update(extra)
    return env


def _kill_process_tree(pid: int) -> None:
    """Best-effort kill of a process and its children (prevents orphaned npm/node trees).

    subprocess timeouts only signal the direct child; grandchildren (e.g. node workers
    spawned by npm) would otherwise survive and pile up — the exact failure observed
    with a 23-minute orphaned npm process.
    """
    import platform

    try:
        if platform.system() == "Windows":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                timeout=15,
            )
        else:
            subprocess.run(["kill", "-9", f"-{pid}"], capture_output=True, timeout=15)
    except Exception:
        pass


def run_command(
    command: list[str],
    cwd: str | None = None,
    timeout: int = 120,
    env: dict | None = None,
    kill_tree: bool = True,
) -> CommandResult:
    """Execute a whitelisted command list with timeout. Raises on blocked patterns.

    On timeout the whole process tree is terminated when kill_tree=True so no
    orphaned grandchildren (npm/node workers) survive.
    """
    joined = " ".join(command).lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in joined:
            raise ValueError(f"Blocked command pattern: {pattern}")
    import time

    start = time.monotonic()
    timed_out = False
    proc = None
    try:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env or sandbox_env(),
            shell=False,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if kill_tree and proc.pid:
                _kill_process_tree(proc.pid)
            try:
                proc.kill()
            except Exception:
                pass
            stdout, stderr = proc.communicate()
            stdout, stderr = stdout or "", stderr or ""
        returncode = proc.returncode if not timed_out else 124
        if timed_out:
            stderr = (stderr + f"\nCommand timed out after {timeout}s (process tree terminated)").strip()
    except (OSError, ValueError) as exc:
        returncode, stdout, stderr = 127, "", f"Failed to start command: {exc}"
    duration = time.monotonic() - start
    return CommandResult(
        command=command,
        returncode=returncode,
        stdout=(stdout or "")[:MAX_OUTPUT_CHARS],
        stderr=(stderr or "")[:MAX_OUTPUT_CHARS],
        duration_s=round(duration, 2),
        timed_out=timed_out,
    )
