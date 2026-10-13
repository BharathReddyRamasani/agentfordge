"""Initial schema: users, projects, workflow_state, requirement_versions, plan_versions,
prototypes, feedback, approvals, agent_tasks, agent_executions, test_runs, debug_records,
reviews, security_checks, project_events, audit_logs, notifications."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

STATUS_ENUM = sa.Enum(
    "CREATED", "ANALYZING", "PLANNING", "PROTOTYPE_BUILDING", "AWAITING_REVIEW",
    "CHANGES_REQUESTED", "PLAN_REVISION", "PROTOTYPE_REBUILDING", "APPROVED",
    "ENGINEERING", "ARCHITECTURE", "FRONTEND_DEVELOPMENT", "BACKEND_DEVELOPMENT",
    "DATABASE_DEVELOPMENT", "INTEGRATION", "TESTING", "DEBUGGING", "REVIEW",
    "SECURITY_VALIDATION", "DOCUMENTATION", "DEPLOYMENT", "COMPLETED", "FAILED",
    "CANCELLED", name="projectstatus", native_enum=False, length=32,
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", STATUS_ENUM, nullable=True),
        sa.Column("current_stage", sa.String(64), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("approved_prototype_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])
    op.create_index("ix_projects_status", "projects", ["status"])

    op.create_table(
        "workflow_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("state", sa.String(48), nullable=True),
        sa.Column("stage_states", sa.JSON(), nullable=True),
        sa.Column("job_id", sa.String(64), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id"),
    )
    op.create_index("ix_workflow_state_project_id", "workflow_state", ["project_id"])

    op.create_table(
        "requirement_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("analysis", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(48), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_requirement_versions_project_id", "requirement_versions", ["project_id"])

    op.create_table(
        "plan_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("revision_of", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_plan_versions_project_id", "plan_versions", ["project_id"])

    op.create_table(
        "prototypes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("plan_version", sa.Integer(), nullable=True),
        sa.Column("requirements_version", sa.Integer(), nullable=True),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_prototypes_project_id", "prototypes", ["project_id"])

    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("prototype_version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("addressed_in_plan_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_feedback_project_id", "feedback", ["project_id"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("artifact_type", sa.String(64), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("stage", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("artifact_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_artifacts_project_id", "artifacts", ["project_id"])
    op.create_index("ix_artifacts_type", "artifacts", ["artifact_type"])

    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("prototype_version", sa.Integer(), nullable=False),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_approvals_project_id", "approvals", ["project_id"])

    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("agent", sa.String(64), nullable=True),
        sa.Column("stage", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    for col in ("project_id", "agent", "stage", "status"):
        op.create_index(f"ix_agent_tasks_{col}", "agent_tasks", [col])

    op.create_table(
        "agent_executions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("agent", sa.String(64), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_executions_project_id", "agent_executions", ["project_id"])
    op.create_index("ix_agent_executions_agent", "agent_executions", ["agent"])

    op.create_table(
        "test_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("run_id", sa.String(64), nullable=True),
        sa.Column("iteration", sa.Integer(), nullable=True),
        sa.Column("total", sa.Integer(), nullable=True),
        sa.Column("passed", sa.Integer(), nullable=True),
        sa.Column("failed", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_test_runs_project_id", "test_runs", ["project_id"])
    op.create_index("ix_test_runs_run_id", "test_runs", ["run_id"])

    op.create_table(
        "debug_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("run_id", sa.String(64), nullable=True),
        sa.Column("iteration", sa.Integer(), nullable=True),
        sa.Column("diagnosis", sa.Text(), nullable=True),
        sa.Column("fix_applied", sa.Text(), nullable=True),
        sa.Column("component", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_debug_records_project_id", "debug_records", ["project_id"])
    op.create_index("ix_debug_records_run_id", "debug_records", ["run_id"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("iteration", sa.Integer(), nullable=True),
        sa.Column("requirement_compliance", sa.String(32), nullable=True),
        sa.Column("architecture_consistency", sa.String(32), nullable=True),
        sa.Column("implementation_completeness", sa.String(32), nullable=True),
        sa.Column("code_quality", sa.String(32), nullable=True),
        sa.Column("verdict", sa.String(32), nullable=True),
        sa.Column("findings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reviews_project_id", "reviews", ["project_id"])

    op.create_table(
        "security_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("iteration", sa.Integer(), nullable=True),
        sa.Column("verdict", sa.String(32), nullable=True),
        sa.Column("critical_issues", sa.Integer(), nullable=True),
        sa.Column("checks", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_security_checks_project_id", "security_checks", ["project_id"])

    op.create_table(
        "project_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("stage", sa.String(64), nullable=True),
        sa.Column("agent", sa.String(64), nullable=True),
        sa.Column("event", sa.String(64), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_project_events_project_id", "project_events", ["project_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_project_id", "audit_logs", ["project_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("type", sa.String(64), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_project_id", "notifications", ["project_id"])
    op.create_index("ix_notifications_read", "notifications", ["read"])


def downgrade() -> None:
    for table in (
        "notifications", "audit_logs", "project_events", "security_checks", "reviews",
        "debug_records", "test_runs", "agent_executions", "agent_tasks", "approvals",
        "feedback", "prototypes", "plan_versions", "requirement_versions",
        "artifacts", "workflow_state", "projects", "users",
    ):
        op.drop_table(table)
    STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
