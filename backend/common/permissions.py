"""Role-based permissions.

Roles (see accounts.User.Role):
- admin: everything
- sales: own leads/contacts/companies/activities/tasks
- support: tickets, plus read-only contacts
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsAdminRole(BasePermission):
    """Only users with role=admin."""

    message = "Only admins can do this."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin)


class RolePermission(BasePermission):
    """Checks the view's role lists.

    A view declares:
      allowed_roles   - roles with full access (admin is always allowed)
      read_only_roles - roles limited to GET/HEAD/OPTIONS
    """

    message = "Your role does not have access to this."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_admin or user.role in getattr(view, "allowed_roles", ()):
            return True
        return request.method in SAFE_METHODS and user.role in getattr(view, "read_only_roles", ())
