"""Consistent API error format.

Every error response looks like:
    {"error": {"code": "not_found", "message": "Not found.", "details": {...} | null}}
"""

from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler


def _error_code(exc: Exception) -> str:
    if isinstance(exc, Http404):
        return "not_found"
    if isinstance(exc, PermissionDenied):
        return "permission_denied"
    if isinstance(exc, APIException):
        codes = exc.get_codes()
        # A single specific code (e.g. "no_active_account"); field errors give a dict/list.
        return codes if isinstance(codes, str) else exc.default_code
    return "error"


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = exception_handler(exc, context)
    if response is None:
        return None  # Unhandled -> Django returns 500.

    data = response.data
    code = _error_code(exc)
    if isinstance(data, dict) and "detail" in data and len(data) == 1:
        message, details = str(data["detail"]), None
    else:
        message, details = "Validation failed.", data

    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
