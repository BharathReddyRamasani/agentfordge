"""Agent output contracts: engineering & quality agents (4, 8-14)."""

from pydantic import BaseModel, Field


class FileArtifact(BaseModel):
    path: str
    content: str


class CodeGenResult(BaseModel):
    """Structured output of code-generation agents (frontend/backend/database/tests/docs/deploy)."""

    files: list[FileArtifact] = []
    notes: str = ""


class ApiEndpoint(BaseModel):
    method: str
    path: str
    description: str = ""
    auth_required: bool = True


class BackendDesignResult(BaseModel):
    """API design produced by the Backend Agent (AGENT 6); materialized by the codegen service."""

    endpoints: list[ApiEndpoint] = []
    notes: str = ""


class FrontendDesignResult(BaseModel):
    """Page/component design produced by the Frontend Agent (AGENT 5); materialized by codegen."""

    pages: list[str] = []
    components: list[str] = []
    notes: str = ""


class ArchitectureResult(BaseModel):
    """System architecture produced by the Architecture Agent (AGENT 4)."""

    summary: str = ""
    frontend_architecture: str = ""
    backend_architecture: str = ""
    database_architecture: str = ""
    api_endpoints: list[ApiEndpoint] = []
    modules: list[str] = []
    dependencies: list[str] = []
    auth_architecture: str = ""
    integration_architecture: str = ""
    deployment_architecture: str = ""


class ReviewFinding(BaseModel):
    severity: str = "info"
    area: str = ""
    finding: str
    suggestion: str = ""


class ReviewResult(BaseModel):
    """Structured review results from the Review/Critic Agent (AGENT 11)."""

    requirement_compliance: str = "pass"
    architecture_consistency: str = "pass"
    implementation_completeness: str = "pass"
    code_quality: str = "pass"
    findings: list[ReviewFinding] = []
    verdict: str = "approved"


class SecurityCheck(BaseModel):
    area: str
    status: str = "pass"
    detail: str = ""


class SecurityResult(BaseModel):
    """Security & quality validation from the Security/Quality Agent (AGENT 12)."""

    checks: list[SecurityCheck] = []
    critical_issues: int = 0
    verdict: str = "pass"


class IntegrationCheck(BaseModel):
    area: str
    status: str = "pass"
    detail: str = ""


class IntegrationResult(BaseModel):
    """Integration validation from the Integration Agent (AGENT 8)."""

    api_connectivity: str = "pass"
    data_flow: str = "pass"
    auth_flow: str = "pass"
    checks: list[IntegrationCheck] = []
    issues_fixed: list[str] = []


class DebugDiagnosis(BaseModel):
    """Diagnosis/fix output of the Debugging Agent (AGENT 10)."""

    root_cause: str = ""
    responsible_component: str = ""
    fix_applied: str = ""
    files_modified: list[str] = []
