"""Project routes: CRUD, requirements, and prototype-validation-loop triggers.

Canonical Phase-2 paths are implemented; short aliases (/analyze, /plan, /prototype,
/feedback, /approve) are kept for compatibility. Both map to the same handlers.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import audit, get_current_user, get_owned_project
from app.core.database import get_db
from app.models.artifacts import Approval, Feedback, PlanVersion, Prototype, RequirementVersion
from app.models.project import Project, ProjectStatus, WorkflowState
from app.models.user import User
from app.orchestrator.state import get_or_create_workflow
from app.schemas.common import MessageResponse
from app.schemas.project import (
    ApproveInput,
    FeedbackInput,
    ProjectCreate,
    ProjectList,
    ProjectPublic,
    RequirementInput,
    RequirementPublic,
)
from app.schemas.workflow import AnalysisPublic, PlanPublic, PrototypePublic, PrototypeValidationPublic, PrototypeVersionPublic
from app.workers.queue import get_job_queue

router = APIRouter(prefix="/api/projects", tags=["projects"])

APPROVAL_STATES = {ProjectStatus.AWAITING_REVIEW, ProjectStatus.CHANGES_REQUESTED}


def _public(project: Project) -> ProjectPublic:
    return ProjectPublic(
        id=project.id, name=project.name, description=project.description or "",
        status=project.status, current_stage=project.current_stage or "",
        progress=project.progress, approved_prototype_version=project.approved_prototype_version,
        created_at=project.created_at, updated_at=project.updated_at, owner_id=project.owner_id,
    )


JOB_STAGE = {"analyze": "analyze", "plan": "plan", "prototype": "prototype", "feedback": "prototype"}

ENGINEERING_ACTIVE = {
    "ENGINEERING", "ARCHITECTURE", "FRONTEND_DEVELOPMENT", "BACKEND_DEVELOPMENT",
    "DATABASE_DEVELOPMENT", "INTEGRATION", "TESTING", "DEBUGGING", "REVIEW",
    "SECURITY_VALIDATION", "DOCUMENTATION", "DEPLOYMENT",
}


def _trigger(db: Session, project: Project, job_type: str, params: dict | None = None, force: bool = False) -> dict:
    import uuid

    wf = get_or_create_workflow(db, project)
    # Duplicate-job guard: never enqueue a second job while the same phase is running.
    # force=True is reserved for the retry endpoint after it verified no active lease.
    if not force:
        stage = JOB_STAGE.get(job_type)
        if stage and (wf.stage_states or {}).get(stage) == "running":
            raise HTTPException(status_code=409, detail=f"A {job_type} job is already running for this project")
        if job_type == "engineering" and project.status.value in ENGINEERING_ACTIVE:
            raise HTTPException(status_code=409, detail="Engineering is already running for this project")
    wf.cancel_requested = False
    wf.job_id = f"{job_type}-{uuid.uuid4().hex[:8]}"
    db.commit()
    job = {"project_id": project.id, "job_type": job_type, "params": params or {}}
    get_job_queue().enqueue(job)
    return {"status": "started", "job_type": job_type}


# ------------------------------------------------------------------ CRUD

@router.post("", response_model=ProjectPublic, status_code=201)
def create_project(payload: ProjectCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = Project(owner_id=user.id, name=payload.name.strip(), description=payload.description or "", status=ProjectStatus.CREATED)
    db.add(project)
    db.commit()
    db.refresh(project)
    get_or_create_workflow(db, project)
    audit(db, user.id, project.id, "project_created", f"name={project.name}")
    return _public(project)


@router.get("", response_model=ProjectList)
def list_projects(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = db.query(Project).filter(Project.owner_id == user.id)
    total = base.count()
    rows = base.order_by(desc(Project.updated_at)).offset(offset).limit(limit).all()
    return ProjectList(items=[_public(p) for p in rows], total=total)


@router.get("/{project_id}", response_model=ProjectPublic)
def get_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _public(get_owned_project(project_id, user, db))


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    audit(db, user.id, project.id, "project_deleted", f"name={project.name}")
    db.delete(project)
    db.commit()
    return None


# ------------------------------------------------------- requirements

@router.post("/{project_id}/requirements", response_model=RequirementPublic, status_code=201)
def submit_requirement(project_id: int, payload: RequirementInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    version = db.query(RequirementVersion).filter(RequirementVersion.project_id == project.id).count() + 1
    req = RequirementVersion(project_id=project.id, version=version, content=payload.description.strip(), source="user", status="captured")
    db.add(req)
    db.commit()
    db.refresh(req)
    audit(db, user.id, project.id, "requirement_submitted", f"version={version}")
    return RequirementPublic(id=req.id, version=req.version, content=req.content, status=req.status, created_at=req.created_at)


@router.get("/{project_id}/requirements", response_model=list[RequirementPublic])
def list_requirements(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    rows = db.query(RequirementVersion).filter(RequirementVersion.project_id == project.id).order_by(RequirementVersion.version).all()
    return [RequirementPublic(id=r.id, version=r.version, content=r.content, status=r.status, created_at=r.created_at) for r in rows]


# ------------------------------------------------------------- analyze

def _start_analysis(project_id: int, user: User, db: Session):
    project = get_owned_project(project_id, user, db)
    if project.status not in (ProjectStatus.CREATED, ProjectStatus.ANALYZING, ProjectStatus.FAILED, ProjectStatus.CANCELLED):
        raise HTTPException(status_code=409, detail=f"Analysis cannot start from state {project.status.value}")
    audit(db, user.id, project.id, "analysis_started", "")
    return _trigger(db, project, "analyze")


@router.post("/{project_id}/requirements/analyze", response_model=MessageResponse, status_code=202)
def analyze_requirement(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _start_analysis(project_id, user, db)
    return MessageResponse(status="started", message="Requirement analysis started")


@router.post("/{project_id}/analyze", response_model=MessageResponse, status_code=202, include_in_schema=False)
def analyze_requirement_alias(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _start_analysis(project_id, user, db)
    return MessageResponse(status="started", message="Requirement analysis started")


@router.get("/{project_id}/analysis", response_model=AnalysisPublic)
def get_analysis(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    req = db.query(RequirementVersion).filter(RequirementVersion.project_id == project.id).order_by(desc(RequirementVersion.version)).first()
    if req is None or req.analysis is None:
        raise HTTPException(status_code=404, detail="No analysis available yet")
    return AnalysisPublic(version=req.version, analysis=req.analysis, created_at=req.created_at)


# --------------------------------------------------------------- plan

def _start_planning(project_id: int, user: User, db: Session):
    project = get_owned_project(project_id, user, db)
    if project.status not in (ProjectStatus.PLANNING, ProjectStatus.ANALYZING, ProjectStatus.FAILED, ProjectStatus.CANCELLED):
        raise HTTPException(status_code=409, detail=f"Planning cannot start from state {project.status.value}")
    audit(db, user.id, project.id, "planning_started", "")
    return _trigger(db, project, "plan")


@router.post("/{project_id}/planning", response_model=MessageResponse, status_code=202)
def start_planning(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _start_planning(project_id, user, db)
    return MessageResponse(status="started", message="Planning started")


@router.post("/{project_id}/plan", response_model=MessageResponse, status_code=202, include_in_schema=False)
def start_planning_alias(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _start_planning(project_id, user, db)
    return MessageResponse(status="started", message="Planning started")


@router.get("/{project_id}/plan", response_model=PlanPublic)
def get_plan(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    plan = db.query(PlanVersion).filter(PlanVersion.project_id == project.id).order_by(desc(PlanVersion.version)).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="No plan available yet")
    return PlanPublic(version=plan.version, plan=plan.plan, created_at=plan.created_at)


@router.get("/{project_id}/planning", response_model=PlanPublic)
def get_planning(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Canonical planning result endpoint (alias of GET /plan)."""
    return get_plan(project_id, user, db)


# ---------------------------------------------------------- prototype

def _start_prototype(project_id: int, user: User, db: Session):
    project = get_owned_project(project_id, user, db)
    if project.status not in (ProjectStatus.PROTOTYPE_BUILDING, ProjectStatus.PLANNING, ProjectStatus.FAILED, ProjectStatus.CANCELLED):
        raise HTTPException(status_code=409, detail=f"Prototype build cannot start from state {project.status.value}")
    audit(db, user.id, project.id, "prototype_started", "")
    return _trigger(db, project, "prototype")


@router.post("/{project_id}/prototype/generate", response_model=MessageResponse, status_code=202)
def generate_prototype(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _start_prototype(project_id, user, db)
    return MessageResponse(status="started", message="Prototype build started")


@router.post("/{project_id}/prototype", response_model=MessageResponse, status_code=202, include_in_schema=False)
def generate_prototype_alias(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _start_prototype(project_id, user, db)
    return MessageResponse(status="started", message="Prototype build started")


def _latest_validation(db: Session, project_id: int, version: int) -> dict | None:
    from app.models.validation import PrototypeValidation

    row = (
        db.query(PrototypeValidation)
        .filter(PrototypeValidation.project_id == project_id, PrototypeValidation.prototype_version == version)
        .order_by(desc(PrototypeValidation.id))
        .first()
    )
    if row is None:
        return None
    return {"version": row.prototype_version, "verdict": row.verdict, "checks": row.checks or [], "created_at": row.created_at}


def _prototype_public(db: Session, project: Project) -> PrototypePublic:
    rows = db.query(Prototype).filter(Prototype.project_id == project.id).order_by(desc(Prototype.version)).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No prototype built yet")
    latest = rows[0]
    versions = [PrototypeVersionPublic(version=r.version, status=r.status, created_at=r.created_at) for r in reversed(rows)]
    return PrototypePublic(id=latest.id, version=latest.version, status=latest.status, spec=latest.spec, created_at=latest.created_at, versions=versions, validation=_latest_validation(db, project.id, latest.version))


@router.post("/{project_id}/prototype/validate", response_model=PrototypeValidationPublic)
def validate_prototype_version(project_id: int, version: int | None = Query(None), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """(Re)run automated validation for a built prototype version without rebuilding it."""
    from app.models.validation import PrototypeValidation
    from app.services.prototype_validation import validate_prototype_html

    project = get_owned_project(project_id, user, db)
    query = db.query(Prototype).filter(Prototype.project_id == project.id)
    proto = query.filter(Prototype.version == version).first() if version is not None else query.order_by(desc(Prototype.version)).first()
    if proto is None:
        raise HTTPException(status_code=404, detail="No prototype built yet")
    report = validate_prototype_html(proto.path, proto.spec if isinstance(proto.spec, dict) else {})
    row = PrototypeValidation(project_id=project.id, prototype_version=proto.version, verdict=report.verdict, checks=[c.dump() for c in report.checks])
    db.add(row)
    proto.status = "ready" if report.verdict == "pass" else "needs_attention"
    db.commit()
    db.refresh(row)
    audit(db, user.id, project.id, "prototype_validated", f"version={proto.version} verdict={report.verdict}")
    return PrototypeValidationPublic(version=row.prototype_version, verdict=row.verdict, checks=row.checks or [], created_at=row.created_at)


@router.get("/{project_id}/prototype", response_model=PrototypePublic)
def get_prototype(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    return _prototype_public(db, project)


@router.get("/{project_id}/prototype/versions", response_model=list[PrototypeVersionPublic])
def list_prototype_versions(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    rows = db.query(Prototype).filter(Prototype.project_id == project.id).order_by(Prototype.version).all()
    return [PrototypeVersionPublic(version=r.version, status=r.status, created_at=r.created_at) for r in rows]


# --------------------------------------------------- feedback + approve

def _submit_feedback(project_id: int, payload: FeedbackInput, user: User, db: Session):
    project = get_owned_project(project_id, user, db)
    if project.status not in APPROVAL_STATES:
        raise HTTPException(status_code=409, detail=f"Feedback is only accepted while a prototype awaits review (current: {project.status.value})")
    audit(db, user.id, project.id, "feedback_submitted", payload.feedback[:300])
    return _trigger(db, project, "feedback", {"feedback": payload.feedback.strip()})


@router.post("/{project_id}/prototype/feedback", response_model=MessageResponse, status_code=202)
def submit_feedback(project_id: int, payload: FeedbackInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _submit_feedback(project_id, payload, user, db)
    return MessageResponse(status="started", message="Change request accepted — revising plan and rebuilding prototype")


@router.post("/{project_id}/feedback", response_model=MessageResponse, status_code=202, include_in_schema=False)
def submit_feedback_alias(project_id: int, payload: FeedbackInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _submit_feedback(project_id, payload, user, db)
    return MessageResponse(status="started", message="Change request accepted — revising plan and rebuilding prototype")


def _approve(project_id: int, payload: ApproveInput, user: User, db: Session):
    from app.models.notification import Notification
    from app.models.validation import PrototypeValidation

    project = get_owned_project(project_id, user, db)
    if project.status not in APPROVAL_STATES:
        raise HTTPException(status_code=409, detail=f"Approval is only possible while a prototype awaits review (current: {project.status.value})")
    latest = db.query(Prototype).filter(Prototype.project_id == project.id).order_by(desc(Prototype.version)).first()
    if latest is None:
        raise HTTPException(status_code=409, detail="No prototype to approve yet")
    # Version pinning: approving a stale (non-latest) version is rejected safely
    if payload.prototype_version is not None and payload.prototype_version != latest.version:
        raise HTTPException(status_code=409, detail=f"Prototype v{payload.prototype_version} is stale; the latest reviewable version is v{latest.version}")
    proto = latest
    # Readiness gate: only a prototype that passed mandatory validation may be approved
    validation = (
        db.query(PrototypeValidation)
        .filter(PrototypeValidation.project_id == project.id, PrototypeValidation.prototype_version == proto.version)
        .order_by(desc(PrototypeValidation.id))
        .first()
    )
    if validation is None or validation.verdict != "pass":
        raise HTTPException(status_code=409, detail=f"Prototype v{proto.version} has not passed mandatory validation and cannot be approved")
    # Duplicate-approval guard: only one approval per prototype version
    existing = db.query(Approval).filter(Approval.project_id == project.id, Approval.prototype_version == proto.version).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Prototype v{proto.version} was already approved")
    approval = Approval(project_id=project.id, prototype_version=proto.version, approved_by=user.id, comment=payload.comment or "")
    db.add(approval)
    project.approved_prototype_version = proto.version
    db.commit()
    db.refresh(approval)
    from app.orchestrator.state import transition

    transition(db, project, ProjectStatus.APPROVED)
    wf = db.query(WorkflowState).filter(WorkflowState.project_id == project.id).first()
    if wf:
        wf.state = "APPROVED"
        db.commit()
    db.add(Notification(user_id=user.id, project_id=project.id, type="approval", title=f"Prototype v{proto.version} approved", message="The approved prototype is now the source of truth for engineering."))
    db.commit()
    audit(db, user.id, project.id, "prototype_approved", f"version={proto.version}")
    return approval


@router.post("/{project_id}/prototype/approve", response_model=MessageResponse)
def approve_prototype(project_id: int, payload: ApproveInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    approval = _approve(project_id, payload, user, db)
    return MessageResponse(status="approved", message=f"Prototype v{approval.prototype_version} approved — engineering may now start")


@router.post("/{project_id}/approve", response_model=MessageResponse, include_in_schema=False)
def approve_prototype_alias(project_id: int, payload: ApproveInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    approval = _approve(project_id, payload, user, db)
    return MessageResponse(status="approved", message=f"Prototype v{approval.prototype_version} approved — engineering may now start")


# ------------------------------------------------- engineering control

@router.post("/{project_id}/engineering/start", response_model=MessageResponse, status_code=202)
def start_engineering(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    if project.status != ProjectStatus.APPROVED:
        raise HTTPException(status_code=409, detail=f"Engineering starts only after explicit prototype approval (current: {project.status.value})")
    audit(db, user.id, project.id, "engineering_started", "")
    _trigger(db, project, "engineering")
    return MessageResponse(status="started", message="Autonomous engineering started")


@router.post("/{project_id}/cancel", response_model=MessageResponse)
def cancel_workflow(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    wf = get_or_create_workflow(db, project)
    if project.status in (ProjectStatus.COMPLETED, ProjectStatus.FAILED, ProjectStatus.CANCELLED, ProjectStatus.CREATED):
        raise HTTPException(status_code=409, detail=f"Nothing running to cancel (current: {project.status.value})")
    if not wf.job_id:
        raise HTTPException(status_code=409, detail="No active workflow job to cancel — the project is waiting (for review, approval, or its next step), not running")
    wf.cancel_requested = True
    db.commit()
    audit(db, user.id, project.id, "workflow_cancel_requested", f"job={wf.job_id}")
    return MessageResponse(status="cancelling", message="Cancellation requested — the running workflow will stop at the next checkpoint")


@router.post("/{project_id}/retry", response_model=MessageResponse, status_code=202)
def retry_workflow(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    wf = get_or_create_workflow(db, project)
    # Legitimate waiting states (user action pending) are not failures — retry is meaningless
    if project.status in (ProjectStatus.CREATED, ProjectStatus.PLANNING, ProjectStatus.AWAITING_REVIEW, ProjectStatus.APPROVED, ProjectStatus.COMPLETED):
        raise HTTPException(status_code=409, detail=f"Retry is only available for failed, cancelled, or interrupted workflows (current: {project.status.value})")
    if project.status not in (ProjectStatus.FAILED, ProjectStatus.CANCELLED):
        # Stuck recovery: a non-terminal state with no active job lease means the worker
        # was interrupted (crash/restart) mid-job — safe to resume, regeneration is idempotent
        if wf.job_id:
            raise HTTPException(status_code=409, detail=f"A workflow job ({wf.job_id}) is still active; cancel it before retrying")
    has_analysis = db.query(RequirementVersion).filter(RequirementVersion.project_id == project.id, RequirementVersion.analysis.isnot(None)).count() > 0
    has_plan = db.query(PlanVersion).filter(PlanVersion.project_id == project.id).count() > 0
    approved = project.approved_prototype_version is not None
    if approved:
        job_type, params = "engineering", {}
    elif project.status in (ProjectStatus.CHANGES_REQUESTED, ProjectStatus.PLAN_REVISION, ProjectStatus.PROTOTYPE_REBUILDING):
        # Resume an interrupted revision loop with the unaddressed feedback text
        pending_fb = db.query(Feedback).filter(Feedback.project_id == project.id, Feedback.addressed_in_plan_version.is_(None)).order_by(desc(Feedback.id)).first()
        if pending_fb is None:
            job_type, params = "prototype", {}
        else:
            job_type, params = "feedback", {"feedback": pending_fb.content}
    elif has_plan:
        job_type, params = "prototype", {}
    elif has_analysis:
        job_type, params = "plan", {}
    else:
        job_type, params = "analyze", {}
    audit(db, user.id, project.id, "workflow_retry", f"job={job_type}")
    # Clear any stale running markers so the resumed job passes the duplicate guard
    states = dict(wf.stage_states or {})
    for key, value in list(states.items()):
        if value == "running":
            states[key] = "pending"
    wf.stage_states = states
    db.commit()
    # force=True only for stale-resume (lease verified absent above); FAILED/CANCELLED
    # pass the guard naturally since no job can be running in a terminal state
    _trigger(db, project, job_type, params, force=project.status not in (ProjectStatus.FAILED, ProjectStatus.CANCELLED))
    return MessageResponse(status="started", message=f"Workflow resumed with job '{job_type}'")
