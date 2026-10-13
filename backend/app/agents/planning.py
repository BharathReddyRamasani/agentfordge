"""AGENT 2 — Planning Agent (initial planning AND plan revision — no separate revision agent)."""

from app.agents.base import BaseAgent
from app.agents.prompts.prototype_phase import PLAN_REVISION_PROMPT, PLANNING_PROMPT
from app.schemas.plan import PlanningResult


class PlanningAgent(BaseAgent):
    name = "Planning Agent"
    stage = "plan"
    output_schema = PlanningResult
    rag_types = ["requirement", "plan", "feedback", "prototype", "approval"]

    def system_prompt(self) -> str:
        return PLAN_REVISION_PROMPT if self.task == "revise_plan" else PLANNING_PROMPT

    def retrieval_query(self, payload_input: dict) -> str:
        parts = [str(payload_input.get("feedback", ""))[:200]]
        analysis = payload_input.get("analysis", {}) or {}
        parts.append(str(analysis.get("purpose", ""))[:200])
        return " | ".join(p for p in parts if p)

    def run_initial(self, db, project, analysis: dict) -> PlanningResult:
        self.task = "plan_application"
        return self.run(db, project, {"analysis": analysis, "project_name": project.name})

    def run_revision(self, db, project, analysis: dict, current_plan: dict, feedback: str) -> PlanningResult:
        """Plan revision: preserves approved requirements while incorporating user feedback."""
        self.task = "revise_plan"
        return self.run(
            db,
            project,
            {"analysis": analysis, "current_plan": current_plan, "feedback": feedback, "project_name": project.name},
        )
