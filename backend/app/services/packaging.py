"""Packaging service: builds ZIP archives for the download center."""

import zipfile
from pathlib import Path

from app.services import workspace

PACKAGE_NAMES = {
    "prototype": "Prototype.zip",
    "application": "Application.zip",
    "docs": "Documentation.zip",
    "deployment": "DeploymentFiles.zip",
    "full": "AgentForge_Project.zip",
}

# Legacy files from the retired vanilla-HTML frontend generator. They remain in old
# workspaces for provenance but must never ship inside deliverable archives.
LEGACY_EXCLUDED = {
    "application/frontend/app.js",
    "application/frontend/config.js",
    "application/frontend/styles.css",
}

# Rebuildable / environment-specific content that must never be zipped.
# (node_modules caused a 3.7 GB corrupt archive and a stuck DEPLOYMENT stage.)
EXCLUDED_DIR_NAMES = {"node_modules", ".git", "__pycache__", ".vite", ".turbo"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo")
EXCLUDED_NAMES = {".DS_Store", "Thumbs.db"}


def build_zip(project_id: int, kind: str) -> Path:
    """Build (or rebuild) a ZIP archive for the given package kind."""
    if kind not in PACKAGE_NAMES:
        raise ValueError(f"Unknown package kind: {kind}")
    root = workspace.project_root(project_id)
    artifacts_root = workspace.artifacts_dir(project_id)
    artifacts_root.mkdir(parents=True, exist_ok=True)
    target = artifacts_root / PACKAGE_NAMES[kind]

    folder_map = {
        "prototype": [("prototype", "prototype/")],
        "application": [("application", "application/")],
        "deployment": [("application/deployment", "deployment/")],
    }

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        added: set[str] = set()

        def _add_file(file: Path, arcname: str) -> None:
            if arcname in added or arcname in LEGACY_EXCLUDED:
                return
            parts = arcname.split("/")
            if any(p in EXCLUDED_DIR_NAMES for p in parts):
                return
            if file.suffix in EXCLUDED_SUFFIXES or file.name in EXCLUDED_NAMES:
                return
            added.add(arcname)
            zf.write(file, arcname)

        if kind == "docs":
            # Documentation ships inside the generated application it describes.
            readme = root / "application" / "README.md"
            if readme.exists():
                _add_file(readme, "README.md")
            docs_src = root / "application" / "docs"
            if docs_src.exists():
                for file in sorted(docs_src.rglob("*")):
                    if file.is_file():
                        _add_file(file, "docs/" + file.relative_to(docs_src).as_posix())
        elif kind in folder_map:
            for src_name, arc_prefix in folder_map[kind]:
                src = root / src_name
                if src.exists():
                    for file in sorted(src.rglob("*")):
                        if file.is_file():
                            _add_file(file, arc_prefix + file.relative_to(src).as_posix())
        elif kind == "full":
            for sub, prefix in [
                ("prototype", "prototype/"),
                ("application", "application/"),
                ("documentation", "documentation/"),
                ("deployment", "deployment/"),
                ("artifacts", "artifacts/"),
                ("tests", "tests/"),
            ]:
                src = root / sub
                if src.exists():
                    for file in sorted(src.rglob("*")):
                        if file.is_file():
                            _add_file(file, prefix + file.relative_to(src).as_posix())
            for name in ("requirements.json", "plan.json", "architecture.json", "README.md"):
                f = artifacts_root / name
                if f.exists():
                    _add_file(f, f"artifacts/{name}")
    return target


def ensure_artifact_files(project_id: int, files: dict[str, str]) -> None:
    """Persist structured artifact JSON files (requirements.json, plan.json, ...)."""
    artifacts_root = workspace.artifacts_dir(project_id)
    artifacts_root.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        path = artifacts_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
