"""Workflow API schemas."""

from datetime import datetime

from pydantic import BaseModel


class StageStatus(BaseModel):
    key: str
    label: str
    status: str


class WorkflowStatus(BaseModel):
    status: str
    stage: str
    progress: int
    current_agent: str | None
    stages: list[StageStatus]
    last_error: str | None = None
    cancel_requested: bool = False
    active_job: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AgentStatusPublic(BaseModel):
    agent: str
    stage: str
    status: str
    attempts: int
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None


class ProjectEventPublic(BaseModel):
    id: int
    stage: str
    agent: str
    event: str
    message: str
    status: str
    progress: int
    created_at: datetime


class PrototypeVersionPublic(BaseModel):
    version: int
    status: str
    created_at: datetime


class PrototypeValidationPublic(BaseModel):
    version: int
    verdict: str
    checks: list[dict] = []
    created_at: datetime


class PrototypePublic(BaseModel):
    id: int
    version: int
    status: str
    spec: dict
    created_at: datetime
    versions: list[PrototypeVersionPublic] = []
    validation: dict | None = None


class PlanPublic(BaseModel):
    version: int
    plan: dict
    created_at: datetime


class AnalysisPublic(BaseModel):
    version: int
    analysis: dict
    created_at: datetime


class TestRunPublic(BaseModel):
    run_id: str
    iteration: int
    total: int
    passed: int
    failed: int
    status: str
    output: str
    created_at: datetime


class ArtifactPublic(BaseModel):
    id: int
    artifact_type: str
    name: str
    version: int
    stage: str
    size: int
    created_at: datetime


class SSEEvent(BaseModel):
    event: str = "info"
    event_type: str = "info"
    stage: str = ""
    agent: str = ""
    message: str = ""
    status: str = "ok"
    progress: int = 0
    project_id: int = 0
    timestamp: str = ""
    payload: dict = {}


class ReviewPublic(BaseModel):
    id: int
    iteration: int
    requirement_compliance: str
    architecture_consistency: str
    implementation_completeness: str
    code_quality: str
    verdict: str
    findings: list[dict] = []
    created_at: datetime


class SecurityPublic(BaseModel):
    id: int
    iteration: int
    verdict: str
    critical_issues: int
    checks: list[dict] = []
    created_at: datetime


class DebugPublic(BaseModel):
    id: int
    run_id: str
    iteration: int
    diagnosis: str
    fix_applied: str
    component: str
    created_at: datetime


class MemoryBlock(BaseModel):
    artifact_type: str
    source: str
    version: int
    score: float
    text: str


class NotificationPublic(BaseModel):
    id: int
    project_id: int | None
    type: str
    title: str
    message: str
    read: bool
    created_at: datetime


class DownloadPackage(BaseModel):
    kind: str
    filename: str
    size: int
    url: str
