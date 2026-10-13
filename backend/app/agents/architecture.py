"""AGENT 4 — Architecture Agent."""

from app.agents.base import BaseAgent
from app.agents.prompts.engineering_phase import ARCHITECTURE_PROMPT
from app.schemas.engineering import ArchitectureResult


class ArchitectureAgent(BaseAgent):
    name = "Architecture Agent"
    stage = "architecture"
    task = "design_architecture"
    output_schema = ArchitectureResult
    rag_types = ["requirement", "plan", "prototype", "analysis"]

    def system_prompt(self) -> str:
        return ARCHITECTURE_PROMPT

    def retrieval_query(self, payload_input: dict) -> str:
        analysis = payload_input.get("analysis", {}) or {}
        plan = payload_input.get("plan", {}) or {}
        return f"{analysis.get('project_name', '')} | {plan.get('summary', '')[:250]}"
