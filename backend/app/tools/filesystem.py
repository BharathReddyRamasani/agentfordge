"""Filesystem tool: sandboxed access restricted to a project workspace root."""

from pathlib import Path


class PathTraversalError(Exception):
    pass


class WorkspaceFS:
    """Provides safe file operations confined to one generated project's workspace."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise PathTraversalError(f"Path escapes workspace sandbox: {relative_path}")
        return candidate

    def ensure_dir(self, relative_path: str) -> Path:
        path = self._resolve(relative_path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_file(self, relative_path: str, content: str) -> Path:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def read_file(self, relative_path: str) -> str:
        path = self._resolve(relative_path)
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        return path.read_text(encoding="utf-8")

    def exists(self, relative_path: str) -> bool:
        try:
            return self._resolve(relative_path).exists()
        except PathTraversalError:
            return False

    def list_tree(self, relative_path: str = ".") -> list[str]:
        path = self._resolve(relative_path)
        if not path.exists():
            return []
        entries: list[str] = []
        for item in sorted(path.rglob("*")):
            rel = item.relative_to(self.root).as_posix()
            entries.append(rel + ("/" if item.is_dir() else ""))
        return entries

    def size(self, relative_path: str) -> int:
        try:
            return self._resolve(relative_path).stat().st_size
        except (FileNotFoundError, PathTraversalError):
            return 0
