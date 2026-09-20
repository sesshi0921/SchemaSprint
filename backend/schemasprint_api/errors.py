from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def problem_response(
    request: Request,
    status_code: int,
    code: str,
    title: str,
    *,
    detail: str | None = None,
    retryable: bool = False,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    body: dict[str, Any] = {
        "type": f"urn:schemasprint:error:{code.lower()}",
        "title": title,
        "status": status_code,
        "code": code,
        "requestId": request_id,
        "retryable": retryable,
    }
    if detail is not None:
        body["detail"] = detail
    return JSONResponse(
        body, status_code=status_code, media_type="application/problem+json"
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = exc.detail if isinstance(exc.detail, str) else "REQUEST_REJECTED"
    return problem_response(request, exc.status_code, code, "Request rejected")


async def request_validation_handler(
    request: Request, _: RequestValidationError
) -> JSONResponse:
    """Return a stable validation problem without reflecting submitted values."""

    return problem_response(
        request,
        422,
        "REQUEST_VALIDATION_FAILED",
        "Request rejected",
    )
