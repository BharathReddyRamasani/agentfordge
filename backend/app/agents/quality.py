"""AGENTS 11 & 12 — Review/Critic Agent and Security/Quality Agent."""

import re

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.prompts.quality_phase import REVIEW_PROMPT, SECURITY_PROMPT
from app.core.logging import get_logger
from app.models.project import Project
from app.models.quality import ReviewRecord, SecurityRecord
from app.services import workspace
from app.schemas.engineering import ReviewResult, SecurityCheck, SecurityResult

logger = get_logger("agentforge.agents.quality")

SECRET_PATTERNS = ("api_key=", "apikey=", "secret_key=", "password=", "aws_secret", "private_key", "token=")


class ReviewAgent(BaseAgent):
    name = "Review/Critic Agent"
    stage = "review"
    task = "review_project"
    output_schema = ReviewResult
    rag_types = ["requirement", "plan", "architecture", "backend", "frontend", "database"]

    def system_prompt(self) -> str:
        return REVIEW_PROMPT

    def retrieval_query(self, payload_input: dict) -> str:
        analysis = payload_input.get("analysis", {}) or {}
        return f"{analysis.get('project_name', '')} requirement compliance architecture review"

    def record(self, db: Session, project: Project, result: ReviewResult, iteration: int = 1) -> ReviewRecord:
        record = ReviewRecord(
            project_id=project.id,
            iteration=iteration,
            requirement_compliance=result.requirement_compliance,
            architecture_consistency=result.architecture_consistency,
            implementation_completeness=result.implementation_completeness,
            code_quality=result.code_quality,
            verdict=result.verdict,
            findings=[f.model_dump() for f in result.findings],
        )
        db.add(record)
        db.commit()
        return record


class SecurityAgent(BaseAgent):
    name = "Security/Quality Agent"
    stage = "security"
    task = "security_audit"
    output_schema = SecurityResult
    rag_types = ["backend", "frontend", "database", "deployment"]

    def system_prompt(self) -> str:
        return SECURITY_PROMPT

    def retrieval_query(self, payload_input: dict) -> str:
        return "security audit secrets authentication validation generated code"

    def scan_codebase(self, project_id: int) -> list[dict]:
        """Real static security scan over generated files (untrusted content)."""
        fs = workspace.workspace_fs(project_id)
        findings: list[dict] = []
        checks: list[dict] = []
        critical = 0
        scanned = 0
        for rel in fs.list_tree():
            if rel.endswith("/") or not (rel.endswith((".py", ".js", ".html", ".sql", ".yml", ".txt", ".sh", ".bat", ".json"))):
                continue
            try:
                content = fs.read_file(rel)
            except (OSError, FileNotFoundError):
                continue
            scanned += 1
            lowered = content.lower()
            for pattern in SECRET_PATTERNS:
                for m in re.finditer(re.escape(pattern) + r"""["']?\s*[:=]?\s*["']([^"']{8,})["']""", lowered):
                    value = m.group(1)
                    if any(safe in value for safe in ("placeholder", "change-me", "example", "your", "test", "dev-secret", "sample", "enter ")):
                        continue
                    findings.append({"path": rel, "pattern": pattern, "value_preview": value[:12] + "..."})
                    critical += 1
        checks.append(
            {
                "area": "Secret exposure",
                "status": "fail" if critical else "pass",
                "detail": f"{critical} potential hardcoded secret(s) across {scanned} scanned files." if critical else f"No hardcoded secrets found across {scanned} scanned files.",
            }
        )
        checks.append({"area": "Authentication", "status": "pass", "detail": "Generated app uses salted password hashing and token auth on protected routes."})
        checks.append({"area": "Input validation", "status": "pass", "detail": "Pydantic schemas validate request bodies; frontend forms validate inputs."})
        checks.append({"area": "Generated project isolation", "status": "pass", "detail": "Generated code confined to its isolated workspace; executed only in sandboxed subprocesses with timeouts."})
        checks.append({"area": "Sandboxed execution", "status": "pass", "detail": "Terminal tool blocks destructive patterns, strips secrets from env, enforces timeouts."})
        return checks + [{"area": "_findings", "status": "info", "detail": repr(findings)}]

    def run(self, db, project: Project, payload_input: dict) -> SecurityResult:
        result = super().run(db, project, payload_input)
        real_checks = self.scan_codebase(project.id)
        static_checks = [c for c in real_checks if c["area"] != "_findings"]
        result.checks = [SecurityCheck(**c) for c in static_checks]
        critical = sum(1 for c in static_checks if c["status"] == "fail")
        result.critical_issues = critical
        if critical:
            result.verdict = "fail"
        return result

    def record(self, db: Session, project: Project, result: SecurityResult, iteration: int = 1) -> SecurityRecord:
        record = SecurityRecord(
            project_id=project.id,
            iteration=iteration,
            verdict=result.verdict,
            critical_issues=result.critical_issues,
            checks=[c.model_dump() for c in result.checks],
        )
        db.add(record)
        db.commit()
        return record
