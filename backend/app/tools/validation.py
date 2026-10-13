"""Validation tool: agent output schema validation and safe-path checks."""

import json
import re
from pathlib import PurePosixPath

from pydantic import BaseModel, ValidationError

UNSAFE_PATH_RE = re.compile(r"(\.\.|~|\^|\0)")


def validate_output(raw: str, schema: type[BaseModel]) -> tuple[BaseModel | None, str]:
    """Validate an LLM/agent JSON output against a schema.

    Returns (validated_model, error_message). error_message is empty on success.
    """
    data = extract_json(raw)
    if data is None:
        return None, "Output does not contain a valid JSON object"
    try:
        return schema.model_validate(data), ""
    except ValidationError as exc:
        errors = []
        for err in exc.errors()[:10]:
            loc = ".".join(str(p) for p in err.get("loc", []))
            errors.append(f"{loc or 'root'}: {err.get('msg', 'invalid')}")
        return None, "Schema validation failed: " + "; ".join(errors)


def extract_json(raw: str) -> dict | None:
    """Extract the first JSON object from an LLM response, tolerating markdown fences."""
    if not raw:
        return None
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            return None
        text = text[start : end + 1]
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def validate_file_path(path: str) -> tuple[bool, str]:
    """Check a generated file path is safe (relative, no traversal, no absolute)."""
    if not path or not path.strip():
        return False, "Empty file path"
    if UNSAFE_PATH_RE.search(path):
        return False, f"Unsafe file path: {path}"
    pure = PurePosixPath(path)
    if pure.is_absolute() or path.startswith("/") or path.startswith("\\") or ":" in path.split("/")[0]:
        return False, f"Absolute file paths are not allowed: {path}"
    return True, ""
