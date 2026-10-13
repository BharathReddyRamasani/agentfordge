"""AGENT 3 — Product/UX & Prototype Build Agent."""

from app.core.logging import get_logger
from app.agents.base import BaseAgent
from app.agents.prompts.prototype_phase import PROTOTYPE_PROMPT
from app.models.artifacts import Artifact
from app.models.project import Project
from app.rag.pipeline import rag_pipeline
from app.schemas.prototype import PrototypeSpec
from app.services import workspace
from app.services.codegen.prototype_renderer import render_prototype
from app.models.user import utcnow

logger = get_logger("agentforge.agents.prototype")


class PrototypeAgent(BaseAgent):
    name = "Product/UX & Prototype Agent"
    stage = "prototype"
    task = "build_prototype"
    output_schema = PrototypeSpec
    rag_types = ["requirement", "plan", "feedback", "prototype"]

    def system_prompt(self) -> str:
        return PROTOTYPE_PROMPT

    def retrieval_query(self, payload_input: dict) -> str:
        analysis = payload_input.get("analysis", {}) or {}
        plan = payload_input.get("plan", {}) or {}
        scope = plan.get("prototype_scope", {}) if isinstance(plan, dict) else {}
        screens = ", ".join(s.get("name", "") for s in scope.get("screens", [])[:8])
        return f"{analysis.get('project_name', '')} | {scope.get('goal', '')[:200]} | screens: {screens}"

    def build(self, db, project: Project, analysis: dict, plan: dict) -> tuple[PrototypeSpec, str]:
        """Produce the spec via the LLM provider, then synthesize the runnable HTML prototype."""
        spec = self.run(db, project, {"analysis": analysis, "plan": plan, "project_name": project.name})
        html = render_prototype(spec)
        fs = workspace.workspace_fs(project.id)
        next_version = 1 + (len(project.prototypes) if project.prototypes else 0)
        path = workspace.prototype_version_dir(project.id, next_version) / "index.html"
        fs.write_file(f"prototype/v{next_version}/index.html", html)
        return spec, str(path)

    def record_artifact(self, db, project: Project, version: int, path: str) -> Artifact:
        artifact = Artifact(
            project_id=project.id,
            artifact_type="prototype",
            name=f"prototype/v{version}/index.html",
            path=path,
            version=version,
            stage=self.stage,
            size=0,
            created_at=utcnow(),
        )
        db.add(artifact)
        db.commit()
        return artifact
