"""Project state machine: explicit states, validated transitions, persistence."""

from enum import Enum

from sqlalchemy.orm import Session

from app.models.project import Project, ProjectStatus, WorkflowState


class InvalidTransitionError(Exception):
    pass


# Non-terminal resume targets for FAILED / CANCELLED projects
_RESUME_TARGETS = {
    ProjectStatus.ANALYZING,
    ProjectStatus.PLANNING,
    ProjectStatus.PROTOTYPE_BUILDING,
    ProjectStatus.ENGINEERING,
}

ALLOWED_TRANSITIONS: dict[ProjectStatus, set[ProjectStatus]] = {
    ProjectStatus.CREATED: {ProjectStatus.ANALYZING, ProjectStatus.CANCELLED},
    ProjectStatus.ANALYZING: {ProjectStatus.PLANNING, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    ProjectStatus.PLANNING: {ProjectStatus.PROTOTYPE_BUILDING, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    ProjectStatus.PROTOTYPE_BUILDING: {ProjectStatus.AWAITING_REVIEW, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    # Human approval gate: only explicit approval or an explicit change request
    ProjectStatus.AWAITING_REVIEW: {
        ProjectStatus.CHANGES_REQUESTED,
        ProjectStatus.APPROVED,
        ProjectStatus.FAILED,
        ProjectStatus.CANCELLED,
    },
    ProjectStatus.CHANGES_REQUESTED: {ProjectStatus.PLAN_REVISION, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    ProjectStatus.PLAN_REVISION: {ProjectStatus.PROTOTYPE_REBUILDING, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    ProjectStatus.PROTOTYPE_REBUILDING: {ProjectStatus.AWAITING_REVIEW, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    # Engineering starts ONLY after explicit approval
    ProjectStatus.APPROVED: {ProjectStatus.ENGINEERING, ProjectStatus.CANCELLED},
    ProjectStatus.ENGINEERING: {ProjectStatus.ARCHITECTURE, ProjectStatus.FAILED, ProjectStatus.CANCELLED},    ProjectStatus.ARCHITECTURE: {
        ProjectStatus.FRONTEND_DEVELOPMENT,
        ProjectStatus.BACKEND_DEVELOPMENT,
        ProjectStatus.DATABASE_DEVELOPMENT,
        ProjectStatus.FAILED,
        ProjectStatus.CANCELLED,
    },
    ProjectStatus.FRONTEND_DEVELOPMENT: {ProjectStatus.BACKEND_DEVELOPMENT, ProjectStatus.DATABASE_DEVELOPMENT, ProjectStatus.INTEGRATION, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    ProjectStatus.BACKEND_DEVELOPMENT: {ProjectStatus.FRONTEND_DEVELOPMENT, ProjectStatus.DATABASE_DEVELOPMENT, ProjectStatus.INTEGRATION, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    ProjectStatus.DATABASE_DEVELOPMENT: {ProjectStatus.BACKEND_DEVELOPMENT, ProjectStatus.FRONTEND_DEVELOPMENT, ProjectStatus.INTEGRATION, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    ProjectStatus.INTEGRATION: {ProjectStatus.TESTING, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    ProjectStatus.TESTING: {ProjectStatus.DEBUGGING, ProjectStatus.REVIEW, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    ProjectStatus.DEBUGGING: {ProjectStatus.TESTING, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    ProjectStatus.REVIEW: {ProjectStatus.SECURITY_VALIDATION, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    ProjectStatus.SECURITY_VALIDATION: {ProjectStatus.DOCUMENTATION, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    ProjectStatus.DOCUMENTATION: {ProjectStatus.DEPLOYMENT, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    ProjectStatus.DEPLOYMENT: {ProjectStatus.COMPLETED, ProjectStatus.FAILED, ProjectStatus.CANCELLED},
    ProjectStatus.COMPLETED: set(),
    ProjectStatus.FAILED: _RESUME_TARGETS | {ProjectStatus.CANCELLED},
    ProjectStatus.CANCELLED: _RESUME_TARGETS,
}

# Resume semantics: an interrupted engineering run (stale job, no active lease) may
# restart the pipeline from any in-flow state. Approval provenance is enforced
# separately by the engine via approved_prototype_version.
_ENGINEERING_FLOW = {
    ProjectStatus.ENGINEERING,
    ProjectStatus.ARCHITECTURE,
    ProjectStatus.FRONTEND_DEVELOPMENT,
    ProjectStatus.BACKEND_DEVELOPMENT,
    ProjectStatus.DATABASE_DEVELOPMENT,
    ProjectStatus.INTEGRATION,
    ProjectStatus.TESTING,
    ProjectStatus.DEBUGGING,
    ProjectStatus.REVIEW,
    ProjectStatus.SECURITY_VALIDATION,
    ProjectStatus.DOCUMENTATION,
    ProjectStatus.DEPLOYMENT,
}
for _state in _ENGINEERING_FLOW:
    ALLOWED_TRANSITIONS[_state] = ALLOWED_TRANSITIONS.get(_state, set()) | {ProjectStatus.ENGINEERING}


def can_transition(current: ProjectStatus, target: ProjectStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


def transition(db: Session, project: Project, target: ProjectStatus) -> ProjectStatus:
    """Apply a validated state transition. Raises InvalidTransitionError on illegal moves."""
    if project.status == target:
        return target
    if not can_transition(project.status, target):
        raise InvalidTransitionError(
            f"Illegal state transition {project.status.value} -> {target.value} for project {project.id}"
        )
    project.status = target
    db.commit()
    return target


def get_or_create_workflow(db: Session, project: Project) -> WorkflowState:
    wf = db.query(WorkflowState).filter(WorkflowState.project_id == project.id).first()
    if wf is None:
        wf = WorkflowState(project_id=project.id, state=project.status.value, stage_states={})
        db.add(wf)
        db.commit()
        db.refresh(wf)
    return wf


# Stage definitions: (key, label, project statuses mapped to the stage)
STAGE_DEFS: list[tuple[str, str, set[str]]] = [
    ("analyze", "Requirements", {"ANALYZING"}),
    ("plan", "Planning", {"PLANNING", "PLAN_REVISION"}),
    ("prototype", "Prototype", {"PROTOTYPE_BUILDING", "PROTOTYPE_REBUILDING", "AWAITING_REVIEW", "CHANGES_REQUESTED"}),
    ("architecture", "Architecture", {"ARCHITECTURE"}),
    ("frontend", "Frontend", {"FRONTEND_DEVELOPMENT"}),
    ("backend", "Backend", {"BACKEND_DEVELOPMENT"}),
    ("database", "Database", {"DATABASE_DEVELOPMENT"}),
    ("integration", "Integration", {"INTEGRATION"}),
    ("testing", "Testing", {"TESTING", "DEBUGGING"}),
    ("review", "Review", {"REVIEW"}),
    ("security", "Security", {"SECURITY_VALIDATION"}),
    ("documentation", "Documentation", {"DOCUMENTATION"}),
    ("deployment", "Deployment", {"DEPLOYMENT"}),
]

# Progress weight per stage key (project.progress %) — ordered by engineering execution order
STAGE_WEIGHTS: dict[str, int] = {
    "analyze": 15,
    "plan": 30,
    "prototype": 45,
    "architecture": 52,
    "database": 58,
    "backend": 66,
    "frontend": 74,
    "integration": 80,
    "testing": 86,
    "review": 89,
    "security": 91,
    "documentation": 94,
    "deployment": 97,
}
