"""AGENT 1 — Requirement Analysis Agent."""

from app.agents.base import BaseAgent
from app.agents.prompts.prototype_phase import REQUIREMENT_ANALYSIS_PROMPT
from app.schemas.analysis import RequirementAnalysisResult


class RequirementAnalysisAgent(BaseAgent):
    name = "Requirement Analysis Agent"
    stage = "analyze"
    task = "analyze_requirement"
    output_schema = RequirementAnalysisResult
    rag_types = ["requirement", "feedback"]

    def system_prompt(self) -> str:
        return REQUIREMENT_ANALYSIS_PROMPT

    def retrieval_query(self, payload_input: dict) -> str:
        return str(payload_input.get("requirement", ""))[:500]
