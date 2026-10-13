"""Workflow observability + artifact APIs: status, agents, logs, memory (RAG), testing,
debugging, review, security, documentation, deployment, artifacts, downloads, preview, SSE."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import audit, get_current_user, get_current_user_flexible, get_owned_project
from app.core.database import SessionLocal, get_db
from app.models.artifacts import Artifact
from app.models.events import ProjectEvent
from app.models.execution import AgentTask, DebugRecord, TestRun
from app.models.notification import Notification
from app.models.project import Project, WorkflowState
from app.models.quality import ReviewRecord, SecurityRecord
from app.models.user import User
from app.orchestrator.state import STAGE_DEFS, get_or_create_workflow
from app.rag.pipeline import rag_pipeline
from app.schemas.common import MessageResponse
from app.schemas.workflow import (
    AgentStatusPublic,
    ArtifactPublic,
    DebugPublic,
    DownloadPackage,
    MemoryBlock,
    NotificationPublic,
    ProjectEventPublic,
    ReviewPublic,
    SecurityPublic,
    StageStatus,
    TestRunPublic,
    WorkflowStatus,
)
from app.services import packaging, workspace

router = APIRouter(prefix="/api/projects", tags=["workflow"])


def _stages(wf: WorkflowState | None, project: Project) -> list[StageStatus]:
    states = (wf.stage_states or {}) if wf else {}
    current = project.status.value
    items = []
    for key, label, mapped in STAGE_DEFS:
        if key in states:
            status = states[key]
        elif current in mapped:
            status = "running"
        elif current in ("COMPLETED",):
            status = "completed"
        else:
            status = "pending"
        items.append(StageStatus(key=key, label=label, status=status))
    return items


@router.get("/{project_id}/workflow", response_model=WorkflowStatus)
def get_workflow(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    wf = get_or_create_workflow(db, project)
    last_task = db.query(AgentTask).filter(AgentTask.project_id == project.id).order_by(desc(AgentTask.id)).first()
    current_agent = last_task.agent if last_task and last_task.status == "running" else None
    return WorkflowStatus(
        status=project.status.value, stage=project.current_stage or "", progress=project.progress,
        current_agent=current_agent, stages=_stages(wf, project), last_error=wf.last_error,
        cancel_requested=wf.cancel_requested, active_job=wf.job_id,
        started_at=wf.started_at, finished_at=wf.finished_at,
    )


@router.get("/{project_id}/agents", response_model=list[AgentStatusPublic])
def get_agents(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    rows = db.query(AgentTask).filter(AgentTask.project_id == project.id).order_by(AgentTask.id).all()
    return [AgentStatusPublic(agent=r.agent, stage=r.stage, status=r.status, attempts=r.attempts, error=r.error, started_at=r.started_at, finished_at=r.finished_at) for r in rows]


@router.get("/{project_id}/logs", response_model=list[ProjectEventPublic])
def get_logs(project_id: int, limit: int = Query(200, ge=1, le=2000), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    rows = db.query(ProjectEvent).filter(ProjectEvent.project_id == project.id).order_by(ProjectEvent.id).limit(limit).all()
    return [ProjectEventPublic(id=r.id, stage=r.stage, agent=r.agent, event=r.event, message=r.message, status=r.status, progress=r.progress, created_at=r.created_at) for r in rows]


@router.get("/{project_id}/memory", response_model=list[MemoryBlock])
def get_memory(
    project_id: int, q: str = Query("", max_length=2000), types: str = Query(""),
    top_k: int = Query(8, ge=1, le=50), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    project = get_owned_project(project_id, user, db)
    artifact_types = [t.strip() for t in types.split(",") if t.strip()] or None
    blocks = rag_pipeline.retrieve(project.id, q or project.name, artifact_types=artifact_types, top_k=top_k)
    return [MemoryBlock(artifact_type=b.artifact_type, source=b.source, version=b.version, score=round(b.score, 3), text=b.text) for b in blocks]


@router.get("/{project_id}/testing", response_model=list[TestRunPublic])
def get_testing(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    rows = db.query(TestRun).filter(TestRun.project_id == project.id).order_by(TestRun.id).all()
    return [TestRunPublic(run_id=r.run_id, iteration=r.iteration, total=r.total, passed=r.passed, failed=r.failed, status=r.status, output=r.output or "", created_at=r.created_at) for r in rows]


@router.get("/{project_id}/debugging", response_model=list[DebugPublic])
def get_debugging(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    rows = db.query(DebugRecord).filter(DebugRecord.project_id == project.id).order_by(DebugRecord.id).all()
    return [DebugPublic(id=r.id, run_id=r.run_id, iteration=r.iteration, diagnosis=r.diagnosis, fix_applied=r.fix_applied, component=r.component, created_at=r.created_at) for r in rows]


@router.get("/{project_id}/review", response_model=list[ReviewPublic])
def get_review(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    rows = db.query(ReviewRecord).filter(ReviewRecord.project_id == project.id).order_by(ReviewRecord.id).all()
    return [ReviewPublic(id=r.id, iteration=r.iteration, requirement_compliance=r.requirement_compliance, architecture_consistency=r.architecture_consistency, implementation_completeness=r.implementation_completeness, code_quality=r.code_quality, verdict=r.verdict, findings=r.findings or [], created_at=r.created_at) for r in rows]


@router.get("/{project_id}/security", response_model=list[SecurityPublic])
def get_security(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    rows = db.query(SecurityRecord).filter(SecurityRecord.project_id == project.id).order_by(SecurityRecord.id).all()
    return [SecurityPublic(id=r.id, iteration=r.iteration, verdict=r.verdict, critical_issues=r.critical_issues, checks=r.checks or [], created_at=r.created_at) for r in rows]


def _workspace_files(project_id: int, subdir: str) -> list[dict]:
    root = workspace.project_root(project_id) / subdir
    if not root.exists():
        return []
    items = []
    for f in sorted(root.rglob("*")):
        if f.is_file():
            items.append({"name": f.relative_to(root).as_posix(), "size": f.stat().st_size, "path": f.relative_to(workspace.project_root(project_id)).as_posix()})
    return items


@router.get("/{project_id}/documentation", response_model=list[dict])
def get_documentation(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_project(project_id, user, db)
    # Documentation ships inside the generated application it describes.
    files = []
    app_root = workspace.project_root(project_id) / "application"
    readme = app_root / "README.md"
    if readme.exists():
        files.append({"name": "README.md", "size": readme.stat().st_size, "path": "application/README.md"})
    docs_dir = app_root / "docs"
    if docs_dir.exists():
        for f in sorted(docs_dir.rglob("*")):
            if f.is_file():
                files.append({"name": f.name, "size": f.stat().st_size, "path": "application/docs/" + f.relative_to(docs_dir).as_posix()})
    # legacy workspace-level documentation dir (if present)
    for extra in _workspace_files(project_id, "documentation"):
        if not any(f["path"].endswith(extra["name"]) for f in files):
            files.append(extra)
    return files


@router.get("/{project_id}/deployment", response_model=list[dict])
def get_deployment(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_project(project_id, user, db)
    return _workspace_files(project_id, "application/deployment")


@router.get("/{project_id}/artifacts", response_model=list[ArtifactPublic])
def get_artifacts(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    rows = db.query(Artifact).filter(Artifact.project_id == project.id).order_by(Artifact.id).all()
    return [ArtifactPublic(id=r.id, artifact_type=r.artifact_type, name=r.name, version=r.version, stage=r.stage, size=r.size, created_at=r.created_at) for r in rows]


@router.get("/{project_id}/artifacts/{artifact_id}/download")
def download_artifact(project_id: int, artifact_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_flexible(request, db)
    project = get_owned_project(project_id, user, db)
    row = db.query(Artifact).filter(Artifact.project_id == project.id, Artifact.id == artifact_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    path = Path(row.path)
    if not path.exists() or path.is_dir():
        raise HTTPException(status_code=404, detail="Artifact file is not available for direct download")
    audit(db, user.id, project.id, "artifact_downloaded", f"artifact={row.name}")
    return FileResponse(str(path), filename=Path(row.name).name)


PACKAGE_KINDS = ("prototype", "application", "docs", "deployment", "full")


@router.get("/{project_id}/downloads", response_model=list[DownloadPackage])
def list_downloads(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(project_id, user, db)
    items = []
    for kind in PACKAGE_KINDS:
        filename = packaging.PACKAGE_NAMES[kind]
        path = workspace.artifacts_dir(project.id) / filename
        size = path.stat().st_size if path.exists() else 0
        items.append(DownloadPackage(kind=kind, filename=filename, size=size, url=f"/api/projects/{project.id}/download?type={kind}"))
    return items


@router.get("/{project_id}/download")
def download_package(project_id: int, type: str = Query("full"), request: Request = None, db: Session = Depends(get_db)):
    user = get_current_user_flexible(request, db)
    project = get_owned_project(project_id, user, db)
    if type not in PACKAGE_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown package type '{type}'. Use one of: {', '.join(PACKAGE_KINDS)}")
    try:
        path = packaging.build_zip(project.id, type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Packaging failed: {exc}")
    audit(db, user.id, project.id, "package_downloaded", f"type={type}")
    return FileResponse(str(path), filename=packaging.PACKAGE_NAMES[type], media_type="application/zip")


@router.get("/{project_id}/prototype/preview", response_class=HTMLResponse)
def preview_prototype(project_id: int, version: int | None = Query(None), request: Request = None, db: Session = Depends(get_db)):
    from app.models.artifacts import Prototype

    user = get_current_user_flexible(request, db)
    project = get_owned_project(project_id, user, db)
    query = db.query(Prototype).filter(Prototype.project_id == project.id)
    proto = query.filter(Prototype.version == version).first() if version else query.order_by(desc(Prototype.version)).first()
    if proto is None:
        raise HTTPException(status_code=404, detail="No prototype available yet")
    path = Path(proto.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Prototype file is missing")
    html = path.read_text(encoding="utf-8")
    response = HTMLResponse(content=html)
    from app.core.config import settings

    origins = " ".join(settings.cors_origin_list) or "'self'"
    response.headers["Content-Security-Policy"] = f"frame-ancestors 'self' {origins}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _application_dist(project_id: int) -> Path:
    return workspace.application_dir(project_id) / "frontend" / "dist"


@router.get("/{project_id}/application/preview")
def preview_application(project_id: int, path: str = Query(""), request: Request = None, db: Session = Depends(get_db)):
    """Serve the built full-scale React application (Vite dist) with SPA fallback.

    This is the runnable production frontend generated by the Frontend Agent and
    compiled during engineering — shown live in the results page.
    """
    from fastapi.responses import Response

    user = get_current_user_flexible(request, db)
    project = get_owned_project(project_id, user, db)
    dist = _application_dist(project.id)
    index = dist / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="The full-scale application has not been built yet")
    target = index
    if path:
        candidate = (dist / path)
        try:
            resolved = candidate.resolve()
        except OSError:
            raise HTTPException(status_code=404, detail="Not found")
        if dist.resolve() not in resolved.parents or not resolved.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        target = resolved
    media_type = "text/html"
    if target.suffix == ".js":
        media_type = "application/javascript"
    elif target.suffix == ".css":
        media_type = "text/css"
    elif target.suffix == ".json":
        media_type = "application/json"
    elif target.suffix in (".png", ".jpg", ".jpeg", ".svg", ".ico", ".woff2"):
        media_type = None
    content = target.read_bytes()
    from app.core.config import settings

    origins = " ".join(settings.cors_origin_list) or "'self'"
    headers = {
        "Content-Security-Policy": f"frame-ancestors 'self' {origins}",
        "X-Content-Type-Options": "nosniff",
    }
    return Response(content=content, media_type=media_type, headers=headers)


def _sse_payload(e: ProjectEvent) -> dict:
    return {
        "event": e.event,
        "event_type": e.event,
        "project_id": e.project_id,
        "stage": e.stage,
        "agent": e.agent,
        "message": e.message,
        "status": e.status,
        "progress": e.progress,
        "timestamp": e.created_at.isoformat() if e.created_at else datetime.now(timezone.utc).isoformat(),
        "payload": e.metadata_json or {},
    }


@router.get("/{project_id}/events/stream")
def stream_events(project_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_flexible(request, db)
    get_owned_project(project_id, user, db)

    def event_generator():
        local_db = SessionLocal()
        last_id = 0
        idle_cycles = 0
        try:
            yield f"data: {json.dumps({'event_type': 'connected', 'event': 'connected', 'project_id': project_id, 'message': 'stream connected', 'status': 'ok', 'progress': 0, 'timestamp': datetime.now(timezone.utc).isoformat(), 'payload': {}})}\n\n"
            while True:
                rows = (
                    local_db.query(ProjectEvent)
                    .filter(ProjectEvent.project_id == project_id, ProjectEvent.id > last_id)
                    .order_by(ProjectEvent.id)
                    .limit(100)
                    .all()
                )
                if rows:
                    idle_cycles = 0
                    for row in rows:
                        last_id = max(last_id, row.id)
                        yield f"data: {json.dumps(_sse_payload(row), default=str)}\n\n"
                else:
                    idle_cycles += 1
                    if idle_cycles % 15 == 0:
                        yield ": ping\n\n"
                project = local_db.get(Project, project_id)
                if project is not None and project.status.value in ("COMPLETED", "FAILED", "CANCELLED") and not rows:
                    if idle_cycles > 20:
                        break
                time.sleep(1.0)
        finally:
            local_db.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
