"""Base ViewSet that enforces role permissions and owner scoping."""

from django.db.models import QuerySet
from rest_framework import viewsets

from .permissions import RolePermission


class OwnerScopedViewSet(viewsets.ModelViewSet):
    """CRUD ViewSet where non-admins only see (and change) rows they own.

    Subclasses can set:
      allowed_roles       - roles with full access (admin always has it)
      read_only_roles     - roles that may only read
      unscoped_read_roles - roles that read *all* rows instead of only their own
    and override `scope_queryset` for custom ownership rules.
    """

    permission_classes = [RolePermission]
    allowed_roles: tuple[str, ...] = ("sales",)
    read_only_roles: tuple[str, ...] = ()
    unscoped_read_roles: tuple[str, ...] = ()

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_admin or user.role in self.unscoped_read_roles:
            return queryset
        return self.scope_queryset(queryset, user)

    def scope_queryset(self, queryset: QuerySet, user) -> QuerySet:
        return queryset.filter(owner=user)

    def perform_create(self, serializer) -> None:
        serializer.save(owner=self.request.user)
