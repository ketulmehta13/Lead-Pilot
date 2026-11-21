"""Consistent API error format.

Every error response looks like:
    {"error": {"code": "not_found", "message": "Not found.", "details": {...}}}
"""
from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = exception_handler(exc, context)
    if response is None:
        return None  # Unhandled -> Django returns 500.

    data = response.data
    code = getattr(exc, "default_code", "error")
    if isinstance(data, dict) and "detail" in data and len(data) == 1:
        message, details = str(data["detail"]), None
    else:
        message, details = "Validation failed." if code == "invalid" else str(exc), data

    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
