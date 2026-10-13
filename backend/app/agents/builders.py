"""AGENTS 5, 6, 7 — Frontend, Backend and Database agents.

Each produces a design via the LLM provider, then materializes REAL runnable files
into the isolated project workspace through the deterministic codegen service."""

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.prompts.engineering_phase import BACKEND_PROMPT, DATABASE_PROMPT, FRONTEND_PROMPT
from app.models.artifacts import Artifact
from app.models.project import Project
from app.rag.pipeline import rag_pipeline
from app.schemas.database import DatabaseSchemaResult
from app.schemas.engineering import BackendDesignResult, FrontendDesignResult
from app.services import workspace
from app.services.codegen.backend_app import generate_backend_files
from app.services.codegen.database_sql import generate_database_files
from app.services.codegen.react_app import generate_frontend_files
from app.models.user import utcnow


def _record_dir_artifact(db: Session, project: Project, artifact_type: str, stage: str, version: int = 1, subpath: str | None = None) -> Artifact:
    path = workspace.project_root(project.id) / (subpath or artifact_type)
    artifact = Artifact(
        project_id=project.id,
        artifact_type=artifact_type,
        name=f"{artifact_type}/",
        path=str(path),
        version=version,
        stage=stage,
        size=sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.exists() else 0,
        created_at=utcnow(),
    )
    db.add(artifact)
    db.commit()
    return artifact


def _app_name(analysis: dict, project: Project) -> str:
    return (analysis or {}).get("project_name") or project.name


class DatabaseAgent(BaseAgent):
    name = "Database Agent"
    stage = "database"
    task = "design_database"
    output_schema = DatabaseSchemaResult
    rag_types = ["analysis", "plan", "architecture", "prototype"]

    def system_prompt(self) -> str:
        return DATABASE_PROMPT

    def retrieval_query(self, payload_input: dict) -> str:
        analysis = payload_input.get("analysis", {}) or {}
        return f"{analysis.get('project_name', '')} database schema entities fields relations"

    def materialize(self, db: Session, project: Project, schema: DatabaseSchemaResult, app_name: str) -> dict[str, str]:
        entity_dicts = [e.model_dump() for e in schema.entities]
        files = generate_database_files(entity_dicts, app_name)
        namespaced = {f"application/{p}": c for p, c in files.items()}
        fs = workspace.workspace_fs(project.id)
        for rel_path, content in namespaced.items():
            fs.write_file(rel_path, content)
        _record_dir_artifact(db, project, "database", self.stage, subpath="application/database")
        for rel_path, content in namespaced.items():
            rag_pipeline.index_artifact(
                project.id, "database", 0, 1, self.stage, rel_path, content[:4000], {"path": rel_path}
            )
        return namespaced


class BackendAgent(BaseAgent):
    name = "Backend Agent"
    stage = "backend"
    task = "design_backend"
    output_schema = BackendDesignResult
    rag_types = ["analysis", "architecture", "plan", "database"]

    def system_prompt(self) -> str:
        return BACKEND_PROMPT

    def retrieval_query(self, payload_input: dict) -> str:
        analysis = payload_input.get("analysis", {}) or {}
        return f"{analysis.get('project_name', '')} backend API endpoints auth CRUD"

    def materialize(self, db: Session, project: Project, entities: list[dict], app_name: str) -> dict[str, str]:
        files = generate_backend_files(entities, app_name)
        namespaced = {f"application/{p}": c for p, c in files.items()}
        fs = workspace.workspace_fs(project.id)
        for rel_path, content in namespaced.items():
            fs.write_file(rel_path, content)
        _record_dir_artifact(db, project, "backend", self.stage, subpath="application/backend")
        for rel_path, content in namespaced.items():
            rag_pipeline.index_artifact(
                project.id, "backend", 0, 1, self.stage, rel_path, content[:4000], {"path": rel_path}
            )
        return namespaced


class FrontendAgent(BaseAgent):
    name = "Frontend Agent"
    stage = "frontend"
    task = "design_frontend"
    output_schema = FrontendDesignResult
    rag_types = ["plan", "prototype", "architecture", "analysis"]

    def system_prompt(self) -> str:
        return FRONTEND_PROMPT

    def retrieval_query(self, payload_input: dict) -> str:
        analysis = payload_input.get("analysis", {}) or {}
        return f"{analysis.get('project_name', '')} frontend pages components navigation forms"

    def materialize(self, db: Session, project: Project, entities: list[dict], app_name: str, tagline: str = "", theme: dict | None = None) -> dict[str, str]:
        """Generate the React + Vite + TypeScript application sources."""
        files = generate_frontend_files(entities, app_name, tagline, theme)
        namespaced = {f"application/{p}": c for p, c in files.items()}
        fs = workspace.workspace_fs(project.id)
        for rel_path, content in namespaced.items():
            fs.write_file(rel_path, content)
        _record_dir_artifact(db, project, "frontend", self.stage, subpath="application/frontend")
        for rel_path, content in namespaced.items():
            rag_pipeline.index_artifact(
                project.id, "frontend", 0, 1, self.stage, rel_path, content[:4000], {"path": rel_path}
            )
        return namespaced
