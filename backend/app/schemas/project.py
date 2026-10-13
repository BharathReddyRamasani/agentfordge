"""Project API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.project import ProjectStatus


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class ProjectPublic(BaseModel):
    id: int
    name: str
    description: str
    status: ProjectStatus
    current_stage: str
    progress: int
    approved_prototype_version: int | None
    created_at: datetime
    updated_at: datetime
    owner_id: int


class ProjectList(BaseModel):
    items: list[ProjectPublic]
    total: int


class RequirementInput(BaseModel):
    description: str = Field(min_length=10, max_length=20000)


class RequirementPublic(BaseModel):
    id: int
    version: int
    content: str
    status: str
    created_at: datetime


class FeedbackInput(BaseModel):
    feedback: str = Field(min_length=3, max_length=10000)


class ApproveInput(BaseModel):
    comment: str = ""
    prototype_version: int | None = None
