"""Git tool: repository initialization, commits and history for generated projects."""

from pathlib import Path

from app.tools.terminal import run_command


class GitTool:
    def __init__(self, repo_dir: str | Path):
        self.repo_dir = Path(repo_dir)

    def _git(self, *args: str, timeout: int = 60):
        return run_command(["git", *args], cwd=str(self.repo_dir), timeout=timeout)

    def available(self) -> bool:
        result = run_command(["git", "--version"])
        return result.ok

    def init(self) -> bool:
        if not (self.repo_dir / ".git").exists():
            result = self._git("init")
            if not result.ok:
                return False
            self._git("config", "user.email", "agentforge@local")
            self._git("config", "user.name", "AgentForge")
        return True

    def add_all(self) -> bool:
        return self._git("add", "-A").ok

    def commit(self, message: str) -> bool:
        if not self.init():
            return False
        self.add_all()
        status = self._git("status", "--porcelain")
        if not status.stdout.strip():
            return True
        return self._git("commit", "-m", message).ok

    def log(self, limit: int = 20) -> list[str]:
        result = self._git("log", "--oneline", f"-n{limit}")
        if not result.ok:
            return []
        return [line for line in result.stdout.splitlines() if line.strip()]
