"""AGENTS 13 & 14 — Documentation Agent and Deployment Agent."""

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.prompts.quality_phase import DEPLOYMENT_PROMPT, DOCUMENTATION_PROMPT
from app.core.logging import get_logger
from app.models.project import Project
from app.rag.pipeline import rag_pipeline
from app.schemas.engineering import CodeGenResult
from app.services import workspace
from app.services.codegen.deploy_gen import generate_deployment_files
from app.services.codegen.docs_gen import generate_docs_files
from app.agents.builders import _record_dir_artifact

logger = get_logger("agentforge.agents.delivery")


class DocumentationAgent(BaseAgent):
    name = "Documentation Agent"
    stage = "documentation"
    task = "write_documentation"
    output_schema = CodeGenResult
    rag_types = ["analysis", "plan", "architecture", "database"]

    def system_prompt(self) -> str:
        return DOCUMENTATION_PROMPT

    def retrieval_query(self, payload_input: dict) -> str:
        analysis = payload_input.get("analysis", {}) or {}
        return f"{analysis.get('project_name', '')} documentation README API architecture guide"

    def write_docs(self, db: Session, project: Project, analysis: dict, plan: dict, architecture: dict, entities: list[dict], app_name: str) -> dict[str, str]:
        # Documentation lives INSIDE the generated application it describes.
        files = generate_docs_files(analysis, plan, architecture, entities, app_name)
        namespaced = {f"application/{path}": content for path, content in files.items()}
        fs = workspace.workspace_fs(project.id)
        for rel_path, content in namespaced.items():
            fs.write_file(rel_path, content)
        _record_dir_artifact(db, project, "documentation", self.stage, subpath="application/docs")
        return namespaced


class DeploymentAgent(BaseAgent):
    name = "Deployment Agent"
    stage = "deployment"
    task = "prepare_deployment"
    output_schema = CodeGenResult
    rag_types = ["architecture", "analysis"]

    def system_prompt(self) -> str:
        return DEPLOYMENT_PROMPT

    def retrieval_query(self, payload_input: dict) -> str:
        return "deployment docker compose environment configuration"

    def write_deployment(self, db: Session, project: Project, app_name: str) -> dict[str, str]:
        files = generate_deployment_files(app_name)
        namespaced = {f"application/{p}": c for p, c in files.items()}
        fs = workspace.workspace_fs(project.id)
        for rel_path, content in namespaced.items():
            fs.write_file(rel_path, content)
        _record_dir_artifact(db, project, "deployment", self.stage, subpath="application/deployment")
        return namespaced
