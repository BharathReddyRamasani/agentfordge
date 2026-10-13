"""Centralized API error model. Every error response uses the envelope:

{"error": {"code": ..., "message": "...", "request_id": "...", "details": {...}}}

No stack traces or provider internals ever reach clients; details are logged server-side.
"""

from fastapi import Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from app.core.request_context import request_id_ctx

HTTP_CODE_MAP = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
}


class APIError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def envelope(code: str, message: str, details: dict | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id_ctx.get(),
            "details": details or {},
        }
    }


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=envelope(exc.code, exc.message, exc.details))


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = HTTP_CODE_MAP.get(exc.status_code, "ERROR")
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(status_code=exc.status_code, content=envelope(code, detail))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", []))
        fields.append({"field": loc, "message": err.get("msg", "invalid")})
    return JSONResponse(status_code=422, content=envelope("VALIDATION_ERROR", "Request validation failed", {"fields": fields[:20]}))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import logging

    logging.getLogger("agentforge.main").exception(
        "unhandled error", extra={"event": "unhandled_error", "path": str(request.url.path)}
    )
    return JSONResponse(status_code=500, content=envelope("INTERNAL_ERROR", "Internal server error"))
