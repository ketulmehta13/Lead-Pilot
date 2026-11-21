"""Custom user model.

Declared in Phase 0 so the database starts with it; roles (admin/sales/support)
are added in Phase 1.
"""
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """LeadPilot user."""
