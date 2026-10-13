"""Agent output contract: Requirement Analysis Agent (AGENT 1)."""

from pydantic import BaseModel, Field


class FeatureItem(BaseModel):
    name: str
    description: str = ""


class RequirementItem(BaseModel):
    id: str
    title: str
    description: str = ""


class RequirementAnalysisResult(BaseModel):
    """Structured requirements produced by the Requirement Analysis Agent."""

    project_name: str = Field(min_length=1)
    purpose: str = ""
    target_users: list[str] = []
    user_roles: list[str] = []
    core_value_proposition: str = ""
    essential_features: list[FeatureItem] = []
    primary_user_flow: list[str] = []
    functional_requirements: list[RequirementItem] = []
    non_functional_requirements: list[RequirementItem] = []
    constraints: list[str] = []
    ambiguities: list[str] = []
