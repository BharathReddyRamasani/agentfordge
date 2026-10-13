"""BaseAgent: common framework — system prompts, RAG context retrieval, schema validation,
bounded retries, and observability (agent tasks, executions, events)."""

import json
import time

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.llm.base import BaseLLMProvider
from app.agents.llm.factory import get_llm_provider
from app.core.config import settings
from app.core.logging import get_logger
from app.models.execution import AgentExecution, AgentTask
from app.models.project import Project
from app.models.user import utcnow
from app.orchestrator.events import emit_event
from app.rag.pipeline import rag_pipeline

logger = get_logger("agentforge.agents")


class BaseAgent:
    """All 14 specialized agents inherit from this class; each keeps its own role,
    prompt, output schema, and context-retrieval policy."""

    name: str = "BaseAgent"
    stage: str = ""
    task: str = ""
    output_schema: type[BaseModel]
    rag_types: list[str] = []
    rag_stage_filter: str | None = None

    def __init__(self, provider: BaseLLMProvider | None = None, agent_name: str | None = None):
        self.provider = provider or get_llm_provider(agent_name=agent_name or self.name)

    def system_prompt(self) -> str:
        raise NotImplementedError

    def retrieval_query(self, payload_input: dict) -> str:
        """Construct the RAG query from the task input (not the entire history)."""
        parts = [f"{k}: {str(v)[:220]}" for k, v in payload_input.items() if isinstance(v, str)]
        if not parts:
            parts = [json.dumps(payload_input, default=str)[:400]]
        return " | ".join(parts)

    def structured_context(self, db: Session, project: Project, payload_input: dict) -> str:
        lines = [f"project: {project.name} (id={project.id})", f"project_status: {project.status.value}"]
        for key, value in payload_input.items():
            summary = value if isinstance(value, str) else json.dumps(value, default=str)
            lines.append(f"{key}: {summary[:1600]}")
        return "\n".join(lines)

    def build_context(self, db: Session, project: Project, payload_input: dict) -> dict:
        blocks = rag_pipeline.retrieve(
            project.id,
            self.retrieval_query(payload_input),
            artifact_types=self.rag_types or None,
            stage=self.rag_stage_filter,
        )
        return {
            "context_project": self.structured_context(db, project, payload_input),
            "context_retrieved": rag_pipeline.build_context_section(blocks),
        }

    def run(self, db: Session, project: Project, payload_input: dict) -> BaseModel:
        """Execute the agent: retrieve context, call the LLM provider, validate output,
        record observability. Raises on failure after bounded retries."""
        task = AgentTask(project_id=project.id, agent=self.name, stage=self.stage, status="running", started_at=utcnow(), attempts=1)
        db.add(task)
        db.commit()
        db.refresh(task)
        emit_event(db, project.id, "agent_started", stage=self.stage, agent=self.name, message=f"{self.name} started")
        start = time.monotonic()
        try:
            context = self.build_context(db, project, payload_input)
            payload = {"task": self.task, "input": payload_input, **context}
            result, usage = self.provider.complete_json(
                self.system_prompt(), payload, self.output_schema, self.task, max_retries=settings.max_agent_retries
            )
            duration = round((time.monotonic() - start) * 1000, 1)
            db.add(
                AgentExecution(
                    project_id=project.id,
                    agent=self.name,
                    task_id=task.id,
                    input_payload={"input_keys": sorted(payload_input.keys())},
                    output_payload=json.loads(result.model_dump_json()),
                    duration_ms=duration,
                    tokens_used=int(usage.get("tokens", 0)),
                    status="completed",
                )
            )
            task.status = "completed"
            task.attempts = int(usage.get("attempt", 1))
            task.finished_at = utcnow()
            db.commit()
            emit_event(db, project.id, "agent_completed", stage=self.stage, agent=self.name, message=f"{self.name} completed")
            return result
        except Exception as exc:
            duration = round((time.monotonic() - start) * 1000, 1)
            task.status = "failed"
            task.error = str(exc)[:2000]
            task.attempts = settings.max_agent_retries + 1
            task.finished_at = utcnow()
            db.commit()
            db.add(
                AgentExecution(
                    project_id=project.id,
                    agent=self.name,
                    task_id=task.id,
                    input_payload={"input_keys": sorted(payload_input.keys())},
                    duration_ms=duration,
                    status="failed",
                )
            )
            db.commit()
            emit_event(
                db,
                project.id,
                "agent_failed",
                stage=self.stage,
                agent=self.name,
                message=f"{self.name} failed: {str(exc)[:300]}",
                status="error",
            )
            raise
