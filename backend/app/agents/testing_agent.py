"""AGENT 9 — Testing Agent (generate + execute)."""

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.prompts.quality_phase import TESTING_PROMPT
from app.core.logging import get_logger
from app.models.execution import TestRun
from app.models.project import Project
from app.schemas.engineering import CodeGenResult
from app.services import workspace
from app.services.codegen.tests_gen import generate_tests_files
from app.tools.testing import TestSuiteResult, run_pytest_tests

logger = get_logger("agentforge.agents.testing")


class TestingAgent(BaseAgent):
    name = "Testing Agent"
    stage = "testing"
    task = "generate_tests"
    output_schema = CodeGenResult
    rag_types = ["analysis", "architecture", "requirement", "database"]

    def system_prompt(self) -> str:
        return TESTING_PROMPT

    def retrieval_query(self, payload_input: dict) -> str:
        analysis = payload_input.get("analysis", {}) or {}
        return f"{analysis.get('project_name', '')} tests pytest auth CRUD entities"

    def write_tests(self, db: Session, project: Project, entities: list[dict], app_name: str) -> dict[str, str]:
        files = generate_tests_files(entities, app_name)
        namespaced = {f"application/{p}": c for p, c in files.items()}
        fs = workspace.workspace_fs(project.id)
        for rel_path, content in namespaced.items():
            fs.write_file(rel_path, content)
        return namespaced

    def run_tests(self, db: Session, project: Project, run_id: str, iteration: int) -> TestSuiteResult:
        """Execute the generated test suite in a sandboxed subprocess and record results."""
        app_root = workspace.application_dir(project.id)
        tests_path = app_root / "tests"
        result = run_pytest_tests(str(tests_path), cwd=str(app_root))
        run = TestRun(
            project_id=project.id,
            run_id=run_id,
            iteration=iteration,
            total=result.total,
            passed=result.passed,
            failed=result.failed,
            status=result.status,
            output=result.output[-8000:],
        )
        db.add(run)
        db.commit()
        return result
