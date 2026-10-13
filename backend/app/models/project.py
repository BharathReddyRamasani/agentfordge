"""Project and workflow state models."""

import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import utcnow


class ProjectStatus(str, enum.Enum):
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    PROTOTYPE_BUILDING = "PROTOTYPE_BUILDING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    PLAN_REVISION = "PLAN_REVISION"
    PROTOTYPE_REBUILDING = "PROTOTYPE_REBUILDING"
    APPROVED = "APPROVED"
    ENGINEERING = "ENGINEERING"
    ARCHITECTURE = "ARCHITECTURE"
    FRONTEND_DEVELOPMENT = "FRONTEND_DEVELOPMENT"
    BACKEND_DEVELOPMENT = "BACKEND_DEVELOPMENT"
    DATABASE_DEVELOPMENT = "DATABASE_DEVELOPMENT"
    INTEGRATION = "INTEGRATION"
    TESTING = "TESTING"
    DEBUGGING = "DEBUGGING"
    REVIEW = "REVIEW"
    SECURITY_VALIDATION = "SECURITY_VALIDATION"
    DOCUMENTATION = "DOCUMENTATION"
    DEPLOYMENT = "DEPLOYMENT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, native_enum=False, length=32), default=ProjectStatus.CREATED, index=True
    )
    current_stage: Mapped[str] = mapped_column(String(64), default="")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    approved_prototype_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    requirements = relationship("RequirementVersion", back_populates="project", cascade="all, delete-orphan")
    plans = relationship("PlanVersion", back_populates="project", cascade="all, delete-orphan")
    prototypes = relationship("Prototype", back_populates="project", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="project", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="project", cascade="all, delete-orphan")
    agent_tasks = relationship("AgentTask", back_populates="project", cascade="all, delete-orphan")
    agent_executions = relationship("AgentExecution", back_populates="project", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="project", cascade="all, delete-orphan")
    test_runs = relationship("TestRun", back_populates="project", cascade="all, delete-orphan")
    debug_records = relationship("DebugRecord", back_populates="project", cascade="all, delete-orphan")
    reviews = relationship("ReviewRecord", back_populates="project", cascade="all, delete-orphan")
    security_records = relationship("SecurityRecord", back_populates="project", cascade="all, delete-orphan")
    events = relationship("ProjectEvent", back_populates="project", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="project", cascade="all, delete-orphan")
    workflow = relationship("WorkflowState", back_populates="project", uselist=False, cascade="all, delete-orphan")


class WorkflowState(Base):
    __tablename__ = "workflow_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(48), default="CREATED")
    stage_states: Mapped[dict] = mapped_column(JSON, default=dict)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="workflow")
