"""Request-scoped correlation ID (propagates into structured logs)."""

from contextvars import ContextVar

request_id_ctx: ContextVar[str] = ContextVar("agentforge_request_id", default="-")
