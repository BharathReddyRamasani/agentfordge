"""Workspace service: isolated per-project workspaces and artifact staging."""

from pathlib import Path

from app.core.config import settings
from app.tools.filesystem import WorkspaceFS


def project_root(project_id: int) -> Path:
    path = Path(settings.workspace_dir) / str(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def prototype_dir(project_id: int) -> Path:
    path = project_root(project_id) / "prototype"
    path.mkdir(parents=True, exist_ok=True)
    return path


def prototype_version_dir(project_id: int, version: int) -> Path:
    path = prototype_dir(project_id) / f"v{version}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def application_dir(project_id: int) -> Path:
    path = project_root(project_id) / "application"
    path.mkdir(parents=True, exist_ok=True)
    return path


def artifacts_dir(project_id: int) -> Path:
    path = project_root(project_id) / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir(project_id: int) -> Path:
    path = project_root(project_id) / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def tests_dir(project_id: int) -> Path:
    path = project_root(project_id) / "tests"
    path.mkdir(parents=True, exist_ok=True)
    return path


def docs_dir(project_id: int) -> Path:
    path = project_root(project_id) / "documentation"
    path.mkdir(parents=True, exist_ok=True)
    return path


def deployment_dir(project_id: int) -> Path:
    path = project_root(project_id) / "deployment"
    path.mkdir(parents=True, exist_ok=True)
    return path


def workspace_fs(project_id: int) -> WorkspaceFS:
    return WorkspaceFS(project_root(project_id))
