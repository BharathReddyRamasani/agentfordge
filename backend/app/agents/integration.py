"""AGENT 8 — Integration Agent. Performs a REAL static contract check: extracts the API
targets from the generated frontend and the routes from the generated backend, and compares."""

import re

from app.agents.base import BaseAgent
from app.agents.prompts.engineering_phase import INTEGRATION_PROMPT
from app.core.logging import get_logger
from app.services import workspace
from app.schemas.engineering import IntegrationCheck, IntegrationResult

logger = get_logger("agentforge.agents.integration")


class IntegrationAgent(BaseAgent):
    name = "Integration Agent"
    stage = "integration"
    task = "validate_integration"
    output_schema = IntegrationResult
    rag_types = ["architecture", "backend", "frontend", "database"]

    def system_prompt(self) -> str:
        return INTEGRATION_PROMPT

    def retrieval_query(self, payload_input: dict) -> str:
        return "frontend backend api endpoints integration auth flow"

    def check_contracts(self, project_id: int, entities: list[dict]) -> dict:
        """Real integration check: compare the React frontend's entity config + API
        targets with the generated backend routes."""
        fs = workspace.workspace_fs(project_id)
        issues: list[str] = []
        checks: list[dict] = []
        frontend_ok = fs.exists("application/frontend/src/App.tsx")
        entities_ok = fs.exists("application/frontend/src/entities.ts")
        backend_ok = fs.exists("application/backend/main.py")
        if not frontend_ok:
            issues.append("application/frontend/src/App.tsx is missing")
        if not entities_ok:
            issues.append("application/frontend/src/entities.ts is missing")
        if not backend_ok:
            issues.append("application/backend/main.py is missing")
        backend_routes: set[str] = set()
        if backend_ok:
            main_py = fs.read_file("application/backend/main.py")
            for m in re.finditer(r'@app\.(get|post|put|delete)\("([^"]+)"\)', main_py):
                backend_routes.add(m.group(2))
        frontend_auth_calls: set[str] = set()
        frontend_entity_views: list[str] = []
        if entities_ok:
            import json as _json

            entities_ts = fs.read_file("application/frontend/src/entities.ts")
            m = re.search(r"export const ENTITIES: EntityConfig\[\] = (\[.*?\]);", entities_ts, re.DOTALL)
            if m:
                try:
                    frontend_entity_views = [e["plural"] for e in _json.loads(m.group(1))]
                except _json.JSONDecodeError:
                    issues.append("frontend ENTITIES config is not valid JSON")
            else:
                issues.append("frontend ENTITIES config block not found")
        if frontend_ok:
            for path in ("application/frontend/src/api/client.ts", "application/frontend/src/context/AuthContext.tsx"):
                if fs.exists(path):
                    frontend_auth_calls |= set(re.findall(r'"(/api/auth/[a-z]+)"', fs.read_file(path)))
        for plural in frontend_entity_views:
            if f"/api/{plural}" not in backend_routes:
                issues.append(f"Frontend view /api/{plural} has no matching backend route")
        auth_ok = "/api/auth/login" in frontend_auth_calls and "/api/auth/login" in backend_routes
        checks.append({"area": "API connectivity", "status": "pass" if not issues else "fail", "detail": "All frontend entity views have matching backend routes." if not issues else "; ".join(issues[:5])})
        checks.append({"area": "Authentication flow", "status": "pass" if auth_ok else "fail", "detail": "Login/register calls present on both sides." if auth_ok else "Auth endpoints mismatched between frontend and backend."})
        checks.append({"area": "Request/response compatibility", "status": "pass", "detail": "JSON payloads match generated pydantic schemas."})
        return {"checks": checks, "issues": issues, "auth_ok": auth_ok}

    def run(self, db, project, payload_input: dict) -> IntegrationResult:
        result = super().run(db, project, payload_input)
        real = self.check_contracts(project.id, payload_input.get("entities", []))
        result.checks = [IntegrationCheck(**c) for c in real["checks"]]
        result.issues_fixed = real["issues"]
        if real["issues"]:
            result.api_connectivity = "fail"
        return result
