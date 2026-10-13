"""Central Orchestrator: WorkflowRunner — executes the prototype validation loop and the
full-scale engineering pipeline as background jobs with checkpoints, cancellation,
bounded retries, failure handling, events and audit history."""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.agents import (
    ArchitectureAgent,
    BackendAgent,
    DatabaseAgent,
    DebuggingAgent,
    DeploymentAgent,
    DocumentationAgent,
    FrontendAgent,
    IntegrationAgent,
    PlanningAgent,
    PrototypeAgent,
    RequirementAnalysisAgent,
    ReviewAgent,
    SecurityAgent,
    TestingAgent,
)
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.artifacts import Artifact, Feedback, PlanVersion, Prototype, RequirementVersion
from app.models.project import Project, ProjectStatus, WorkflowState
from app.models.user import utcnow
from app.orchestrator import events as ev
from app.orchestrator.state import InvalidTransitionError, STAGE_WEIGHTS, get_or_create_workflow, transition
from app.rag.pipeline import rag_pipeline
from app.services import packaging, workspace
from app.tools.frontend_build import build_frontend
from app.tools.git_tool import GitTool

logger = get_logger("agentforge.orchestrator")


class WorkflowCancelledError(Exception):
    pass


class WorkflowFailedError(Exception):
    pass


def _latest_requirement(db: Session, project_id: int) -> RequirementVersion | None:
    return (
        db.query(RequirementVersion)
        .filter(RequirementVersion.project_id == project_id)
        .order_by(desc(RequirementVersion.version))
        .first()
    )


def _latest_plan(db: Session, project_id: int) -> PlanVersion | None:
    return (
        db.query(PlanVersion)
        .filter(PlanVersion.project_id == project_id)
        .order_by(desc(PlanVersion.version))
        .first()
    )


def _latest_prototype(db: Session, project_id: int) -> Prototype | None:
    return (
        db.query(Prototype)
        .filter(Prototype.project_id == project_id)
        .order_by(desc(Prototype.version))
        .first()
    )


class WorkflowRunner:
    def __init__(self, db_factory=SessionLocal):
        self.db_factory = db_factory

    # ------------------------------------------------------------- job entry

    def run_job(self, job: dict) -> None:
        project_id = job.get("project_id")
        job_type = job.get("job_type")
        params = job.get("params", {}) or {}
        db: Session = self.db_factory()
        try:
            project = db.get(Project, project_id)
            if project is None:
                logger.error("job references unknown project", extra={"project_id": project_id})
                return
            wf = get_or_create_workflow(db, project)
            self._check_cancel(db, project, wf)
            if job_type == "analyze":
                self._run_analyze(db, project, wf)
            elif job_type == "plan":
                self._run_plan(db, project, wf)
            elif job_type == "prototype":
                self._run_prototype(db, project, wf)
            elif job_type == "feedback":
                self._run_feedback(db, project, wf, params)
            elif job_type == "engineering":
                self._run_engineering(db, project, wf)
            else:
                raise WorkflowFailedError(f"Unknown job type: {job_type}")
        except WorkflowCancelledError:
            try:
                db.rollback()
                project = db.get(Project, project_id)
                if project is not None:
                    wf = get_or_create_workflow(db, project)
                    self._mark_cancelled(db, project, wf)
            except Exception:
                logger.exception("cancel handling crashed", extra={"project_id": project_id})
        except Exception as exc:
            logger.error(
                "workflow job failed",
                extra={"project_id": project_id, "event": job_type, "error": str(exc)[:500]},
            )
            try:
                db.rollback()
                project = db.get(Project, project_id)
                if project is not None:
                    wf = get_or_create_workflow(db, project)
                    self._fail(db, project, wf, f"{job_type} failed: {exc}")
            except Exception:
                logger.exception("failure handling crashed", extra={"project_id": project_id})
        finally:
            # Release the job lease so cancel/retry report truthfully afterwards
            try:
                wf = db.query(WorkflowState).filter(WorkflowState.project_id == project_id).first()
                if wf is not None and wf.job_id:
                    wf.job_id = None
                    db.commit()
            except Exception:
                pass
            db.close()

    # ------------------------------------------------------------- primitives

    def _check_cancel(self, db: Session, project: Project, wf: WorkflowState) -> None:
        db.refresh(wf)
        if wf.cancel_requested:
            self._mark_cancelled(db, project, wf)
            raise WorkflowCancelledError()

    def _mark_cancelled(self, db: Session, project: Project, wf: WorkflowState) -> None:
        """Idempotent cancellation marking (safe to call twice)."""
        changed = project.status != ProjectStatus.CANCELLED
        try:
            transition(db, project, ProjectStatus.CANCELLED)
        except InvalidTransitionError:
            changed = False
        wf.state = "CANCELLED"
        wf.finished_at = utcnow()
        db.commit()
        if changed:
            ev.emit_event(db, project.id, "workflow_cancelled", message="Workflow cancelled by user", status="cancelled", owner_id=project.owner_id, notify=True)

    def _stage_start(self, db: Session, project: Project, wf: WorkflowState, stage: str, message: str, agent: str = "") -> None:
        self._check_cancel(db, project, wf)
        states = dict(wf.stage_states or {})
        states[stage] = "running"
        wf.stage_states = states
        project.current_stage = stage
        db.commit()
        ev.emit_event(db, project.id, "stage_started", stage=stage, agent=agent, message=message)

    def _stage_done(self, db: Session, project: Project, wf: WorkflowState, stage: str, message: str, agent: str = "") -> None:
        states = dict(wf.stage_states or {})
        states[stage] = "completed"
        wf.stage_states = states
        project.progress = STAGE_WEIGHTS.get(stage, project.progress)
        db.commit()
        ev.emit_event(db, project.id, "stage_completed", stage=stage, agent=agent, message=message, progress=project.progress)

    def _fail(self, db: Session, project: Project, wf: WorkflowState, message: str) -> None:
        wf.last_error = message[:2000]
        try:
            if project.status != ProjectStatus.FAILED:
                transition(db, project, ProjectStatus.FAILED)
        except InvalidTransitionError:
            pass
        wf.state = "FAILED"
        wf.finished_at = utcnow()
        db.commit()
        ev.emit_event(db, project.id, "workflow_failed", message=message[:500], status="error", owner_id=project.owner_id, notify=True, notification_type="error")

    def _commit(self, project_id: int, message: str) -> None:
        try:
            GitTool(workspace.project_root(project_id)).commit(message)
        except Exception as exc:
            logger.warning("git commit failed", extra={"project_id": project_id, "error": str(exc)[:200]})

    # --------------------------------------------------- LOOP 1: prototype

    def _run_analyze(self, db: Session, project: Project, wf: WorkflowState) -> None:
        transition(db, project, ProjectStatus.ANALYZING)
        wf.state = "ANALYZING"
        wf.started_at = wf.started_at or utcnow()
        db.commit()
        self._stage_start(db, project, wf, "analyze", "Requirement Analysis Agent started", agent="Requirement Analysis Agent")
        req = _latest_requirement(db, project.id)
        content = req.content if req else (project.description or "")
        if not content.strip():
            raise WorkflowFailedError("No requirement text found for analysis")
        agent = RequirementAnalysisAgent()
        result = agent.run(db, project, {"requirement": content, "project_name": project.name})
        data = json.loads(result.model_dump_json())
        if req is None:
            req = RequirementVersion(project_id=project.id, version=1, content=content, source="user")
            db.add(req)
            db.commit()
            db.refresh(req)
        req.analysis = data
        req.status = "analyzed"
        db.commit()
        rag_pipeline.index_artifact(
            project.id, "analysis", req.id, req.version, "analyze", "requirement_analysis",
            f"{data.get('project_name', '')}. {data.get('purpose', '')} "
            f"Value: {data.get('core_value_proposition', '')} "
            f"Features: {', '.join(f.get('name', '') for f in data.get('essential_features', []))} "
            f"Flow: {' -> '.join(data.get('primary_user_flow', []))}",
            {"version": req.version},
        )
        packaging.ensure_artifact_files(
            project.id,
            {
                "requirements.json": json.dumps({"version": req.version, "content": content}, indent=2),
                "analysis.json": json.dumps(data, indent=2),
            },
        )
        self._commit(project.id, "Requirement analysis complete")
        self._stage_done(db, project, wf, "analyze", "Requirement analysis complete", agent="Requirement Analysis Agent")
        transition(db, project, ProjectStatus.PLANNING)
        wf.state = "PLANNING"
        db.commit()
        ev.emit_event(db, project.id, "analysis_completed", stage="plan", message="Analysis complete — ready for planning")

    def _run_plan(self, db: Session, project: Project, wf: WorkflowState) -> None:
        if project.status != ProjectStatus.PLANNING:
            transition(db, project, ProjectStatus.PLANNING)
        wf.state = "PLANNING"
        db.commit()
        self._stage_start(db, project, wf, "plan", "Planning Agent started", agent="Planning Agent")
        req = _latest_requirement(db, project.id)
        analysis = (req.analysis or {}) if req else {}
        if not analysis:
            raise WorkflowFailedError("No requirement analysis found; run analysis first")
        agent = PlanningAgent()
        result = agent.run_initial(db, project, analysis)
        data = json.loads(result.model_dump_json())
        version = db.query(PlanVersion).filter(PlanVersion.project_id == project.id).count() + 1
        db.add(PlanVersion(project_id=project.id, version=version, plan=data))
        db.commit()
        scope = data.get("prototype_scope", {})
        rag_pipeline.index_artifact(
            project.id, "plan", 0, version, "plan", "planning",
            f"Plan v{version}: {data.get('summary', '')} Goal: {scope.get('goal', '')} "
            f"Screens: {', '.join(s.get('name', '') for s in scope.get('screens', []))}",
            {"version": version},
        )
        packaging.ensure_artifact_files(project.id, {"plan.json": json.dumps(data, indent=2)})
        self._commit(project.id, f"Plan v{version} created")
        self._stage_done(db, project, wf, "plan", f"Development plan v{version} created", agent="Planning Agent")
        transition(db, project, ProjectStatus.PROTOTYPE_BUILDING)
        wf.state = "PROTOTYPE_BUILDING"
        db.commit()

    def _run_prototype(self, db: Session, project: Project, wf: WorkflowState) -> None:
        if project.status != ProjectStatus.PROTOTYPE_BUILDING:
            transition(db, project, ProjectStatus.PROTOTYPE_BUILDING)
        wf.state = "PROTOTYPE_BUILDING"
        db.commit()
        self._stage_start(db, project, wf, "prototype", "Prototype Build Agent started", agent="Product/UX & Prototype Agent")
        req = _latest_requirement(db, project.id)
        plan = _latest_plan(db, project.id)
        if req is None or req.analysis is None:
            raise WorkflowFailedError("No analyzed requirements found")
        if plan is None:
            raise WorkflowFailedError("No plan found; run planning first")
        agent = PrototypeAgent()
        spec, path = agent.build(db, project, req.analysis, plan.plan)
        version = db.query(Prototype).filter(Prototype.project_id == project.id).count() + 1
        proto = Prototype(
            project_id=project.id, version=version, plan_version=plan.version,
            requirements_version=req.version, spec=json.loads(spec.model_dump_json()),
            path=path, status="validating",
        )
        db.add(proto)
        db.commit()
        self._validate_prototype(db, project, proto, version, f"prototype_v{version}")
        agent.record_artifact(db, project, version, path)
        rag_pipeline.index_artifact(
            project.id, "prototype", proto.id, version, "prototype", "prototype_build",
            f"Prototype v{version}: {spec.app_name}. Screens: {', '.join(s.name for s in spec.screens)}. Flow: {' -> '.join(spec.user_flow)}",
            {"version": version},
        )
        packaging.ensure_artifact_files(project.id, {f"prototype_v{version}.json": spec.model_dump_json(indent=2)})
        self._commit(project.id, f"Prototype v{version} built")
        self._stage_done(db, project, wf, "prototype", f"Prototype v{version} built", agent="Product/UX & Prototype Agent")
        transition(db, project, ProjectStatus.AWAITING_REVIEW)
        wf.state = "AWAITING_REVIEW"
        db.commit()
        ev.emit_event(db, project.id, "prototype_ready", stage="prototype", agent="Product/UX & Prototype Agent", message=f"Prototype v{version} is ready for your review", progress=project.progress, owner_id=project.owner_id, notify=True)

    def _run_feedback(self, db: Session, project: Project, wf: WorkflowState, params: dict) -> None:
        feedback_text = str(params.get("feedback", "")).strip()
        if not feedback_text:
            raise WorkflowFailedError("Empty feedback text")
        if project.status not in (ProjectStatus.AWAITING_REVIEW, ProjectStatus.CHANGES_REQUESTED):
            raise WorkflowFailedError(f"Feedback is only accepted while a prototype awaits review (current: {project.status.value})")
        proto = _latest_prototype(db, project.id)
        req = _latest_requirement(db, project.id)
        plan = _latest_plan(db, project.id)
        if proto is None or req is None or plan is None:
            raise WorkflowFailedError("Prototype loop artifacts are incomplete")
        fb = Feedback(project_id=project.id, prototype_version=proto.version, content=feedback_text)
        db.add(fb)
        db.commit()
        rag_pipeline.index_artifact(project.id, "feedback", fb.id, proto.version, "prototype", "user_feedback", f"User feedback on prototype v{proto.version}: {feedback_text}", {"prototype_version": proto.version})
        transition(db, project, ProjectStatus.CHANGES_REQUESTED)
        wf.state = "CHANGES_REQUESTED"
        db.commit()
        ev.emit_event(db, project.id, "changes_requested", stage="prototype", message="Change request received — revising plan")

        # Planning Agent revises the plan (no separate revision agent)
        transition(db, project, ProjectStatus.PLAN_REVISION)
        wf.state = "PLAN_REVISION"
        db.commit()
        self._stage_start(db, project, wf, "plan", "Planning Agent revising plan", agent="Planning Agent")
        agent = PlanningAgent()
        revised = agent.run_revision(db, project, req.analysis or {}, plan.plan, feedback_text)
        revised_data = json.loads(revised.model_dump_json())
        new_version = plan.version + 1
        db.add(PlanVersion(project_id=project.id, version=new_version, plan=revised_data, revision_of=plan.version, feedback=feedback_text))
        db.commit()
        fb.addressed_in_plan_version = new_version
        db.commit()
        rag_pipeline.index_artifact(project.id, "plan", 0, new_version, "plan", "plan_revision", f"Revised plan v{new_version}: {revised_data.get('revision_notes', '')}", {"version": new_version, "revision_of": plan.version})
        packaging.ensure_artifact_files(project.id, {"plan.json": json.dumps(revised_data, indent=2)})
        self._commit(project.id, f"Plan revised to v{new_version}")
        self._stage_done(db, project, wf, "plan", f"Plan revised to v{new_version}", agent="Planning Agent")

        # Prototype rebuild
        transition(db, project, ProjectStatus.PROTOTYPE_REBUILDING)
        wf.state = "PROTOTYPE_REBUILDING"
        db.commit()
        self._stage_start(db, project, wf, "prototype", "Rebuilding prototype from revised plan", agent="Product/UX & Prototype Agent")
        build_agent = PrototypeAgent()
        spec, path = build_agent.build(db, project, req.analysis or {}, revised_data)
        new_proto_version = proto.version + 1
        new_proto = Prototype(
            project_id=project.id, version=new_proto_version, plan_version=new_version,
            requirements_version=req.version, spec=json.loads(spec.model_dump_json()),
            path=path, status="validating",
        )
        db.add(new_proto)
        db.commit()
        self._validate_prototype(db, project, new_proto, new_proto_version, f"prototype_v{new_proto_version}")
        build_agent.record_artifact(db, project, new_proto_version, path)
        rag_pipeline.index_artifact(
            project.id, "prototype", new_proto.id, new_proto_version, "prototype", "prototype_rebuild",
            f"Prototype v{new_proto_version} (rebuilt): {spec.app_name}. Screens: {', '.join(s.name for s in spec.screens)}",
            {"version": new_proto_version},
        )
        packaging.ensure_artifact_files(project.id, {f"prototype_v{new_proto_version}.json": spec.model_dump_json(indent=2)})
        self._commit(project.id, f"Prototype rebuilt as v{new_proto_version}")
        self._stage_done(db, project, wf, "prototype", f"Prototype v{new_proto_version} rebuilt", agent="Product/UX & Prototype Agent")
        transition(db, project, ProjectStatus.AWAITING_REVIEW)
        wf.state = "AWAITING_REVIEW"
        db.commit()
        ev.emit_event(db, project.id, "prototype_ready", stage="prototype", agent="Product/UX & Prototype Agent", message=f"Prototype v{new_proto_version} rebuilt with your requested changes — ready for review", progress=project.progress, owner_id=project.owner_id, notify=True)

    def _validate_prototype(self, db: Session, project: Project, proto: Prototype, version: int, label: str) -> None:
        """Run the automated readiness gate. A prototype failing a mandatory check is
        NEVER presented as ready: the job fails with an actionable report instead."""
        from app.models.validation import PrototypeValidation
        from app.services.prototype_validation import validate_prototype_html

        ev.emit_event(db, project.id, "prototype_validating", stage="prototype", agent="Product/UX & Prototype Agent", message=f"Validating {label} (rendering + interaction checks)")
        report = validate_prototype_html(proto.path, proto.spec if isinstance(proto.spec, dict) else {})
        db.add(PrototypeValidation(project_id=project.id, prototype_version=version, verdict=report.verdict, checks=[c.dump() for c in report.checks]))
        proto.status = "ready" if report.verdict == "pass" else "needs_attention"
        db.commit()
        rag_pipeline.index_artifact(project.id, "prototype_validation", 0, version, "prototype", "prototype_validation", f"{label}: {report.verdict}. {report.summary()}", {"version": version, "verdict": report.verdict})
        if report.verdict != "pass":
            raise WorkflowFailedError(f"{label} failed mandatory prototype validation: {report.summary()}")

    # ------------------------------------------------- LOOP 2: engineering

    def _run_engineering(self, db: Session, project: Project, wf: WorkflowState) -> None:
        # Approval provenance (not just current status): engineering may start fresh from
        # APPROVED or resume from any in-flow state after an interruption — but never
        # without a recorded explicit approval.
        if project.approved_prototype_version is None:
            raise WorkflowFailedError(
                f"Full-scale engineering requires explicit prototype approval (current: {project.status.value})"
            )
        transition(db, project, ProjectStatus.ENGINEERING)
        wf.state = "ENGINEERING"
        wf.started_at = wf.started_at or utcnow()
        db.commit()
        ev.emit_event(db, project.id, "engineering_started", stage="architecture", message="Approved prototype accepted — autonomous engineering started", owner_id=project.owner_id, notify=True)

        req = _latest_requirement(db, project.id)
        plan = _latest_plan(db, project.id)
        analysis = (req.analysis or {}) if req else {}
        plan_data = plan.plan if plan else {}
        app_name = analysis.get("project_name") or project.name
        fs = workspace.workspace_fs(project.id)

        # ---- Architecture
        transition(db, project, ProjectStatus.ARCHITECTURE)
        wf.state = "ARCHITECTURE"
        db.commit()
        self._stage_start(db, project, wf, "architecture", "Architecture Agent started", agent="Architecture Agent")
        arch = ArchitectureAgent().run(db, project, {"analysis": analysis, "plan": plan_data})
        arch_data = json.loads(arch.model_dump_json())
        packaging.ensure_artifact_files(project.id, {"architecture.json": json.dumps(arch_data, indent=2)})
        rag_pipeline.index_artifact(project.id, "architecture", 0, 1, "architecture", "architecture", f"Architecture: {arch_data.get('summary', '')} Modules: {', '.join(arch_data.get('modules', []))}", {})
        self._commit(project.id, "Architecture designed")
        self._stage_done(db, project, wf, "architecture", "System architecture designed", agent="Architecture Agent")

        # ---- Database
        transition(db, project, ProjectStatus.DATABASE_DEVELOPMENT)
        self._stage_start(db, project, wf, "database", "Database Agent started", agent="Database Agent")
        db_agent = DatabaseAgent()
        schema = db_agent.run(db, project, {"analysis": analysis, "plan": plan_data, "architecture": arch_data})
        entities = [e.model_dump() for e in schema.entities]
        db_agent.materialize(db, project, schema, app_name)
        self._commit(project.id, "Database layer generated")
        self._stage_done(db, project, wf, "database", "Database schema and models generated", agent="Database Agent")

        # ---- Backend
        transition(db, project, ProjectStatus.BACKEND_DEVELOPMENT)
        self._stage_start(db, project, wf, "backend", "Backend Agent started", agent="Backend Agent")
        backend_agent = BackendAgent()
        backend_design = backend_agent.run(db, project, {"analysis": analysis, "plan": plan_data, "architecture": arch_data, "entities": entities})
        backend_agent.materialize(db, project, entities, app_name)
        rag_pipeline.index_artifact(project.id, "backend_design", 0, 1, "backend", "backend_design", json.dumps([e.model_dump() for e in backend_design.endpoints])[:4000], {})
        self._commit(project.id, "Backend API generated")
        self._stage_done(db, project, wf, "backend", "Backend API generated", agent="Backend Agent")

        # ---- Frontend (React + Vite + TypeScript sources, then build harness loop)
        transition(db, project, ProjectStatus.FRONTEND_DEVELOPMENT)
        self._stage_start(db, project, wf, "frontend", "Frontend Agent started", agent="Frontend Agent")
        frontend_agent = FrontendAgent()
        tagline = str(analysis.get("core_value_proposition", ""))[:120]
        approved_theme: dict = {}
        latest_proto = _latest_prototype(db, project.id)
        if latest_proto is not None and isinstance(latest_proto.spec, dict):
            approved_theme = latest_proto.spec.get("theme", {}) or {}
        frontend_agent.run(db, project, {"analysis": analysis, "plan": plan_data, "architecture": arch_data, "entities": entities})
        frontend_agent.materialize(db, project, entities, app_name, tagline=tagline, theme=approved_theme)
        self._commit(project.id, "Frontend (React + Vite + TypeScript) generated")

        # Build->fix->rebuild loop (bounded): the generated app must actually compile.
        # Sub-stage progress is streamed as events so long npm/vite runs never look frozen.
        app_root = workspace.application_dir(project.id)

        def _build_phase(info: dict) -> None:
            phase, event = info.get("phase", "?"), info.get("event", "?")
            if event == "started":
                ev.emit_event(db, project.id, f"frontend_{phase}_started", stage="frontend", agent="Frontend Agent", message=f"Frontend {phase.replace('_', ' ')} started")
            else:
                ok = info.get("ok", False)
                ev.emit_event(db, project.id, f"frontend_{phase}_finished", stage="frontend", agent="Frontend Agent", message=f"Frontend {phase.replace('_', ' ')} {'succeeded' if ok else 'failed'} ({info.get('duration_s', 0)}s)", status="ok" if ok else "error")

        def _should_cancel() -> bool:
            db.refresh(wf)
            return bool(wf.cancel_requested)

        from app.tools.frontend_build import BuildCancelled

        try:
            build = build_frontend(app_root, on_phase=_build_phase, should_cancel=_should_cancel)
            build_iter = 1
            max_builds = 2
            while not build.ok and build_iter <= max_builds:
                ev.emit_event(db, project.id, "build_failed", stage="frontend", agent="Debugging Agent", message=f"Frontend build failed (iteration {build_iter}) — debugging", status="error")
                debugging = DebuggingAgent()
                diagnosis = debugging.run(db, project, {"failure_output": build.output[-4000:], "summary": f"vite build iteration {build_iter}"})
                debugging.apply_fix(db, project, entities, app_name, "frontend", tagline=tagline, theme=approved_theme)
                debugging.record(db, project, f"build-{uuid.uuid4().hex[:8]}", build_iter, diagnosis)
                self._commit(project.id, f"Frontend build fix iteration {build_iter}")
                build = build_frontend(app_root, on_phase=_build_phase, should_cancel=_should_cancel)
                build_iter += 1
        except BuildCancelled:
            self._mark_cancelled(db, project, wf)
            raise WorkflowCancelledError()
        if not build.ok:
            raise WorkflowFailedError(f"Generated frontend failed to build after {max_builds} attempt(s): {build.output[-500:]}")
        packaging.ensure_artifact_files(project.id, {"frontend_build.log": build.output[-4000:]})
        self._stage_done(db, project, wf, "frontend", "React frontend generated and built (Vite dist ready)", agent="Frontend Agent")

        # ---- Integration
        transition(db, project, ProjectStatus.INTEGRATION)
        self._stage_start(db, project, wf, "integration", "Integration Agent started", agent="Integration Agent")
        integration = IntegrationAgent().run(db, project, {"analysis": analysis, "architecture": arch_data, "entities": entities})
        if integration.api_connectivity == "fail":
            raise WorkflowFailedError(f"Integration contract check failed: {'; '.join(integration.issues_fixed[:5])}")
        packaging.ensure_artifact_files(project.id, {"integration.json": integration.model_dump_json(indent=2)})
        self._commit(project.id, "Integration verified")
        self._stage_done(db, project, wf, "integration", "Frontend/backend integration verified", agent="Integration Agent")

        # ---- Testing + Debugging loop (bounded)
        transition(db, project, ProjectStatus.TESTING)
        self._stage_start(db, project, wf, "testing", "Testing Agent started", agent="Testing Agent")
        testing = TestingAgent()
        endpoints = [e.model_dump() for e in arch.api_endpoints]
        testing.run(db, project, {"analysis": analysis, "entities": entities, "endpoints": endpoints, "app_name": app_name})
        testing.write_tests(db, project, entities, app_name)
        run_id = uuid.uuid4().hex[:12]
        iteration = 1
        suite = testing.run_tests(db, project, run_id, iteration)
        rag_pipeline.index_artifact(project.id, "test_results", 0, iteration, "testing", "test_run", f"Test run {run_id} iteration {iteration}: {suite.total} tests, {suite.passed} passed, status={suite.status}", {"run_id": run_id, "iteration": iteration})
        while suite.status != "passed" and iteration <= settings.max_debug_iterations:
            transition(db, project, ProjectStatus.DEBUGGING)
            wf.state = "DEBUGGING"
            db.commit()
            self._stage_start(db, project, wf, "debugging", f"Debugging iteration {iteration} started", agent="Debugging Agent")
            debugging = DebuggingAgent()
            diagnosis = debugging.run(db, project, {"failure_output": suite.output[-4000:], "summary": f"run={run_id} total={suite.total} passed={suite.passed} failed={suite.failed}"})
            debugging.apply_fix(db, project, entities, app_name, diagnosis.responsible_component)
            debugging.record(db, project, run_id, iteration, diagnosis)
            rag_pipeline.index_artifact(project.id, "debug_results", 0, iteration, "debugging", "debug_fix", f"Iteration {iteration}: {diagnosis.root_cause}. Fix: {diagnosis.fix_applied}", {"run_id": run_id, "iteration": iteration})
            self._commit(project.id, f"Debug fix iteration {iteration}")
            states = dict(wf.stage_states or {})
            states["debugging"] = "completed"
            wf.stage_states = states
            db.commit()
            transition(db, project, ProjectStatus.TESTING)
            wf.state = "TESTING"
            db.commit()
            self._check_cancel(db, project, wf)
            iteration += 1
            suite = testing.run_tests(db, project, run_id, iteration)
            rag_pipeline.index_artifact(project.id, "test_results", 0, iteration, "testing", "test_run", f"Test run {run_id} iteration {iteration}: {suite.total} tests, {suite.passed} passed, status={suite.status}", {"run_id": run_id, "iteration": iteration})
        if suite.status != "passed":
            raise WorkflowFailedError(f"Tests still failing after {settings.max_debug_iterations} debugging iteration(s): {suite.output[-500:]}")
        packaging.ensure_artifact_files(project.id, {"test_report.json": suite.output[-4000:]})
        self._commit(project.id, "Tests passing")
        self._stage_done(db, project, wf, "testing", f"Test suite passed ({suite.passed}/{suite.total})", agent="Testing Agent")

        # ---- Review
        transition(db, project, ProjectStatus.REVIEW)
        self._stage_start(db, project, wf, "review", "Review Agent started", agent="Review/Critic Agent")
        artifact_rows = db.query(Artifact).filter(Artifact.project_id == project.id).all()
        review_agent = ReviewAgent()
        review = review_agent.run(
            db, project,
            {"analysis": analysis, "architecture": arch_data,
             "artifacts": [a.name for a in artifact_rows],
             "test_summary": f"{suite.total} tests, {suite.passed} passed, status={suite.status}"},
        )
        review_agent.record(db, project, review)
        packaging.ensure_artifact_files(project.id, {"review.json": review.model_dump_json(indent=2)})
        self._stage_done(db, project, wf, "review", f"Review complete: {review.verdict}", agent="Review/Critic Agent")

        # ---- Security
        transition(db, project, ProjectStatus.SECURITY_VALIDATION)
        self._stage_start(db, project, wf, "security", "Security Agent started", agent="Security/Quality Agent")
        security_agent = SecurityAgent()
        security = security_agent.run(db, project, {"app_name": app_name, "root": str(workspace.project_root(project.id))})
        security_agent.record(db, project, security)
        packaging.ensure_artifact_files(project.id, {"security.json": security.model_dump_json(indent=2)})
        if security.critical_issues > 0:
            raise WorkflowFailedError(f"Security audit found {security.critical_issues} critical issue(s)")
        self._stage_done(db, project, wf, "security", "Security validation passed", agent="Security/Quality Agent")

        # ---- Documentation
        transition(db, project, ProjectStatus.DOCUMENTATION)
        self._stage_start(db, project, wf, "documentation", "Documentation Agent started", agent="Documentation Agent")
        docs_agent = DocumentationAgent()
        docs_agent.run(db, project, {"analysis": analysis, "plan": plan_data, "architecture": arch_data, "entities": entities, "app_name": app_name})
        docs_agent.write_docs(db, project, analysis, plan_data, arch_data, entities, app_name)
        self._commit(project.id, "Documentation generated")
        self._stage_done(db, project, wf, "documentation", "Documentation generated", agent="Documentation Agent")

        # ---- Deployment
        transition(db, project, ProjectStatus.DEPLOYMENT)
        self._stage_start(db, project, wf, "deployment", "Deployment Agent started", agent="Deployment Agent")
        deploy_agent = DeploymentAgent()
        deploy_agent.run(db, project, {"app_name": app_name, "analysis": analysis})
        deploy_agent.write_deployment(db, project, app_name)
        self._commit(project.id, "Deployment configuration generated")

        # ---- Final validation + packaging (COMPLETED only when validation succeeds)
        self._check_cancel(db, project, wf)
        required = [
            "application/backend/main.py", "application/backend/database.py", "application/backend/models.py",
            "application/frontend/package.json", "application/frontend/src/App.tsx",
            "application/frontend/dist/index.html", "application/database/schema.sql",
            "application/tests/test_app.py", "application/README.md", "application/deployment/Dockerfile",
        ]
        missing = [r for r in required if not fs.exists(r)]
        missing = [r for r in required if not fs.exists(r)]
        if missing:
            raise WorkflowFailedError(f"Final validation failed — missing generated files: {', '.join(missing)}")
        for kind in ("prototype", "application", "docs", "deployment", "full"):
            packaging.build_zip(project.id, kind)
        self._stage_done(db, project, wf, "deployment", "Deployment prepared and packaged", agent="Deployment Agent")

        transition(db, project, ProjectStatus.COMPLETED)
        wf.state = "COMPLETED"
        wf.finished_at = utcnow()
        project.progress = 100
        db.commit()
        duration = ""
        if wf.started_at:
            started = wf.started_at.replace(tzinfo=timezone.utc) if wf.started_at.tzinfo is None else wf.started_at
            duration = f" in {round((datetime.now(timezone.utc) - started).total_seconds(), 1)}s"
        ev.emit_event(db, project.id, "project_completed", message=f"Project completed successfully{duration} — artifacts ready for download", progress=100, owner_id=project.owner_id, notify=True)
