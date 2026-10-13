"""AGENT 10 — Debugging Agent. Diagnoses failures and applies fixes (bounded re-tests)."""

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.prompts.quality_phase import DEBUGGING_PROMPT
from app.core.logging import get_logger
from app.models.execution import DebugRecord
from app.models.project import Project
from app.schemas.engineering import DebugDiagnosis
from app.services import workspace

logger = get_logger("agentforge.agents.debugging")


class DebuggingAgent(BaseAgent):
    name = "Debugging Agent"
    stage = "debugging"
    task = "diagnose_failure"
    output_schema = DebugDiagnosis
    rag_types = ["test_results", "backend", "frontend", "database"]

    def system_prompt(self) -> str:
        return DEBUGGING_PROMPT

    def retrieval_query(self, payload_input: dict) -> str:
        return str(payload_input.get("failure_output", ""))[:400]

    def apply_fix(self, db: Session, project: Project, entities: list[dict], app_name: str, component: str, tagline: str = "", theme: dict | None = None) -> list[str]:
        """Fix strategy: regenerate the affected component from the approved design."""
        from app.services.codegen.backend_app import generate_backend_files
        from app.services.codegen.database_sql import generate_database_files
        from app.services.codegen.react_app import generate_frontend_files

        fs = workspace.workspace_fs(project.id)
        modified: list[str] = []
        regenerators = {
            "backend": lambda: generate_backend_files(entities, app_name),
            "backend (imports)": lambda: generate_backend_files(entities, app_name),
            "frontend": lambda: generate_frontend_files(entities, app_name, tagline, theme),
            "database": lambda: generate_database_files(entities, app_name),
        }
        regen = regenerators.get(component, regenerators["backend"])
        for rel_path, content in regen().items():
            fs.write_file(f"application/{rel_path}", content)
            modified.append(f"application/{rel_path}")
        return modified

    def record(self, db: Session, project: Project, run_id: str, iteration: int, diagnosis: DebugDiagnosis) -> DebugRecord:
        record = DebugRecord(
            project_id=project.id,
            run_id=run_id,
            iteration=iteration,
            diagnosis=diagnosis.root_cause[:4000],
            fix_applied=diagnosis.fix_applied[:4000],
            component=diagnosis.responsible_component[:120],
        )
        db.add(record)
        db.commit()
        return record
