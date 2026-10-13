"""MockLLMProvider: deterministic offline provider. Produces genuine structured output
by dispatching to mock handlers with the real task inputs. Used for development, tests
and offline operation only."""

import json

from pydantic import BaseModel

from app.agents.llm.base import BaseLLMProvider, LLMValidationError


def _estimate_tokens(payload: dict) -> int:
    return len(json.dumps(payload, default=str)) // 4


class MockLLMProvider(BaseLLMProvider):
    name = "mock"

    def complete(self, system: str, user: str, temperature: float | None = None, max_tokens: int | None = None, timeout: float | None = None) -> str:
        self.last_usage = {"provider": self.name, "model": "mock", "tokens": _estimate_tokens({"s": system, "u": user})}
        return json.dumps({"note": "mock provider: use complete_json for structured tasks"})

    def complete_json(
        self,
        system: str,
        payload: dict,
        schema: type[BaseModel],
        task_name: str,
        max_retries: int = 0,
    ) -> tuple[BaseModel, dict]:
        from app.agents.llm.mock_handlers import HANDLERS

        handler = HANDLERS.get(task_name)
        if handler is None:
            raise LLMValidationError(f"Mock provider has no handler for task '{task_name}'")
        data = handler(payload)
        model = schema.model_validate(data)
        usage = {"provider": self.name, "task": task_name, "tokens": _estimate_tokens(payload)}
        return model, usage
