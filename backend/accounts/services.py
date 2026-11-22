"""Account management: profile, passwords and admin team management.

Guards keep a workspace from locking itself out: admins can't change their own role or
deactivate themselves, and the last active admin can't be demoted or deactivated.
Users are deactivated, never deleted, so their CRM records keep an owner.
"""

from __future__ import annotations

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from .models import User

PROFILE_FIELDS = ("first_name", "last_name", "email")
ADMIN_FIELDS = (*PROFILE_FIELDS, "role", "is_active")


def _check_email(email: str, user: User) -> str:
    email = email.strip().lower()
    if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
        raise ValidationError({"email": ["A user with this email already exists."]})
    return email


def _validate_password(password: str, user: User, field: str) -> None:
    try:
        password_validation.validate_password(password, user)
    except DjangoValidationError as exc:
        raise ValidationError({field: list(exc.messages)}) from exc


def update_profile(user: User, data: dict) -> User:
    """Let any user change their own name and email."""
    changed = []
    for field in PROFILE_FIELDS:
        if field in data:
            value = data[field]
            if field == "email":
                value = _check_email(value, user)
            setattr(user, field, value)
            changed.append(field)
    if changed:
        user.save(update_fields=changed)
    return user


def change_password(user: User, current_password: str, new_password: str) -> None:
    """Change your own password; the current one must be correct."""
    if not user.check_password(current_password):
        raise ValidationError({"current_password": ["Current password is incorrect."]})
    if current_password == new_password:
        raise ValidationError({"new_password": ["Choose a different password."]})
    _validate_password(new_password, user, "new_password")
    user.set_password(new_password)
    user.save(update_fields=["password"])


def _other_active_admins(user: User) -> bool:
    return User.objects.filter(role=User.Role.ADMIN, is_active=True).exclude(pk=user.pk).exists()


def admin_update_user(actor: User, target: User, data: dict) -> User:
    """An admin edits a team member: name, email, role, active/inactive."""
    new_role = data.get("role", target.role)
    new_active = data.get("is_active", target.is_active)
    if target.pk == actor.pk:
        if new_role != target.role:
            raise ValidationError({"role": ["You can't change your own role."]})
        if not new_active:
            raise ValidationError({"is_active": ["You can't deactivate your own account."]})
    losing_admin = (
        target.is_admin and target.is_active and (new_role != User.Role.ADMIN or not new_active)
    )
    if losing_admin and not _other_active_admins(target):
        raise ValidationError({"role": ["The workspace needs at least one active admin."]})

    changed = []
    for field in ADMIN_FIELDS:
        if field in data:
            value = data[field]
            if field == "email":
                value = _check_email(value, target)
            setattr(target, field, value)
            changed.append(field)
    if changed:
        target.save(update_fields=changed)
        target.refresh_from_db(fields=["role"])  # superusers stay admins (User.save)
    return target


def admin_set_password(actor: User, target: User, password: str) -> None:
    """An admin resets a team member's password (e.g. they forgot it)."""
    _validate_password(password, target, "password")
    target.set_password(password)
    target.save(update_fields=["password"])
