"""Shared pytest fixtures."""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts.models import User
from crm.models import Company, Contact, Lead

PASSWORD = "Str0ng-pass!"


@pytest.fixture(autouse=True)
def _fresh_cache():
    """Throttle counters and cached summaries must not leak between tests."""
    cache.clear()
    yield
    cache.clear()


def make_user(username: str, role: str) -> User:
    return User.objects.create_user(
        username=username, password=PASSWORD, email=f"{username}@test.io", role=role
    )


@pytest.fixture
def admin_user(db) -> User:
    return make_user("boss", User.Role.ADMIN)


@pytest.fixture
def rep(db) -> User:
    return make_user("rep1", User.Role.SALES)


@pytest.fixture
def other_rep(db) -> User:
    return make_user("rep2", User.Role.SALES)


@pytest.fixture
def support_user(db) -> User:
    return make_user("helpdesk", User.Role.SUPPORT)


@pytest.fixture
def client_for():
    """client_for(user) -> APIClient authenticated as that user (None = anonymous)."""

    def _client(user: User | None) -> APIClient:
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    return _client


@pytest.fixture
def contact_of():
    """contact_of(user, **fields) -> a Contact (with a Company) owned by `user`."""
    counter = {"n": 0}

    def _make(user: User, **fields) -> Contact:
        counter["n"] += 1
        company = Company.objects.create(owner=user, name=f"Acme {counter['n']}")
        defaults = {
            "first_name": "Asha",
            "last_name": "Rao",
            "email": f"asha{counter['n']}@acme.io",
            "company": company,
        }
        return Contact.objects.create(owner=user, **{**defaults, **fields})

    return _make


@pytest.fixture
def lead_of(contact_of):
    def _make(user: User, **fields) -> Lead:
        contact = fields.pop("contact", None) or contact_of(user)
        return Lead.objects.create(owner=user, contact=contact, **fields)

    return _make
