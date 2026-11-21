"""Custom user model with a CRM role."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """LeadPilot user. `role` drives permissions across the API."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        SALES = "sales", "Sales Rep"
        SUPPORT = "support", "Support"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.SALES)

    def save(self, *args, **kwargs) -> None:
        # Django superusers are always LeadPilot admins.
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def is_sales(self) -> bool:
        return self.role == self.Role.SALES

    @property
    def is_support(self) -> bool:
        return self.role == self.Role.SUPPORT

    def __str__(self) -> str:
        return self.get_full_name() or self.username
