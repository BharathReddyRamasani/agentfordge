"""Agent registry: the 14 logical specialized agent roles + shared base."""

from app.agents.base import BaseAgent
from app.agents.architecture import ArchitectureAgent
from app.agents.builders import BackendAgent, DatabaseAgent, FrontendAgent
from app.agents.debugging import DebuggingAgent
from app.agents.delivery import DeploymentAgent, DocumentationAgent
from app.agents.integration import IntegrationAgent
from app.agents.planning import PlanningAgent
from app.agents.prototype import PrototypeAgent
from app.agents.quality import ReviewAgent, SecurityAgent
from app.agents.requirement_analysis import RequirementAnalysisAgent
from app.agents.testing_agent import TestingAgent

__all__ = [
    "BaseAgent",
    "RequirementAnalysisAgent",
    "PlanningAgent",
    "PrototypeAgent",
    "ArchitectureAgent",
    "FrontendAgent",
    "BackendAgent",
    "DatabaseAgent",
    "IntegrationAgent",
    "TestingAgent",
    "DebuggingAgent",
    "ReviewAgent",
    "SecurityAgent",
    "DocumentationAgent",
    "DeploymentAgent",
]
