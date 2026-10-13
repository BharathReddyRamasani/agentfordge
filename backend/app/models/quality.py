"""Persistent review and security validation records (AGENT 11 / AGENT 12 outputs)."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import utcnow


class ReviewRecord(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    iteration: Mapped[int] = mapped_column(Integer, default=1)
    requirement_compliance: Mapped[str] = mapped_column(String(32), default="pass")
    architecture_consistency: Mapped[str] = mapped_column(String(32), default="pass")
    implementation_completeness: Mapped[str] = mapped_column(String(32), default="pass")
    code_quality: Mapped[str] = mapped_column(String(32), default="pass")
    verdict: Mapped[str] = mapped_column(String(32), default="approved")
    findings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project = relationship("Project", back_populates="reviews")


class SecurityRecord(Base):
    __tablename__ = "security_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    iteration: Mapped[int] = mapped_column(Integer, default=1)
    verdict: Mapped[str] = mapped_column(String(32), default="pass")
    critical_issues: Mapped[int] = mapped_column(Integer, default=0)
    checks: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project = relationship("Project", back_populates="security_records")
