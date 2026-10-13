"""Agent output contract: Planning Agent (AGENT 2)."""

from typing import Literal

from pydantic import BaseModel, Field


class PlanTheme(BaseModel):
    primary_color: str = "#4f46e5"
    accent_color: str = "#0ea5e9"
    background_color: str = "#f8fafc"


class PlanScreen(BaseModel):
    name: str
    purpose: str = ""
    sections: list[str] = []


class PrototypeScope(BaseModel):
    goal: str = ""
    screens: list[PlanScreen] = []
    interactions: list[str] = []
    include: list[str] = []
    out_of_scope: list[str] = []
    theme: PlanTheme | None = None


class PlanPhase(BaseModel):
    name: str
    description: str = ""
    tasks: list[str] = []


class AppStack(BaseModel):
    frontend: str = "React + TypeScript + Tailwind CSS"
    backend: str = "Python FastAPI + SQLAlchemy"
    database: str = "PostgreSQL"


class FullApplicationPlan(BaseModel):
    phases: list[PlanPhase] = []
    stack: AppStack = AppStack()


class FeaturePriority(BaseModel):
    feature: str
    priority: Literal["high", "medium", "low"] = "medium"


class PlanningResult(BaseModel):
    """Development plan produced by the Planning Agent (initial plan or plan revision)."""

    summary: str = ""
    prototype_scope: PrototypeScope = PrototypeScope()
    full_application_plan: FullApplicationPlan = FullApplicationPlan()
    feature_priorities: list[FeaturePriority] = []
    revision_notes: str = ""
