"""Security sweep: every API endpoint requires auth (except an explicit allowlist), roles are
enforced, login is rate-limited and no secret leaks into responses."""

import re

import pytest
from django.core.cache import cache
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from conftest import PASSWORD

pytestmark = pytest.mark.django_db

# Endpoints that are intentionally reachable without a token.
PUBLIC = {
    ("/api/health/", "get"),
    ("/api/auth/login/", "post"),
    ("/api/auth/refresh/", "post"),
    ("/api/billing/webhook/", "post"),  # no login, but the HMAC signature is required
}


def api_operations() -> list[tuple[str, str]]:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    ops = []
    for path, methods in schema["paths"].items():
        for method in methods:
            if method in {"get", "post", "put", "patch", "delete"}:
                ops.append((path, method))
    return sorted(ops)


def concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


def test_schema_lists_the_whole_api():
    ops = api_operations()
    paths = {p for p, _ in ops}
    for prefix in ("/api/crm/", "/api/ml/", "/api/genai/", "/api/agent/", "/api/billing/",
                   "/api/support/", "/api/analytics/", "/api/auth/"):  # fmt: skip
        assert any(p.startswith(prefix) for p in paths), prefix
    assert len(ops) > 60


@pytest.mark.parametrize(("path", "method"), api_operations())
def test_anonymous_requests_are_rejected(path, method):
    if (path, method) in PUBLIC:
        pytest.skip("public by design")
    response = getattr(APIClient(), method)(concrete(path), {}, format="json")
    assert response.status_code in (401, 403), f"{method.upper()} {path} -> {response.status_code}"


def test_public_endpoints_still_protect_themselves(client_for):
    client = client_for(None)
    assert client.post("/api/billing/webhook/", {}, format="json").status_code == 400
    assert client.post("/api/auth/login/", {"username": "x", "password": "y"},
                       format="json").status_code == 401  # fmt: skip
    assert client.post("/api/auth/refresh/", {"refresh": "nope"}, format="json").status_code == 401


SALES_ONLY_LISTS = [
    "/api/crm/companies/", "/api/crm/leads/", "/api/crm/deals/", "/api/crm/activities/",
    "/api/crm/tasks/", "/api/analytics/summary/", "/api/ml/metrics/", "/api/agent/runs/",
    "/api/billing/invoices/",
]  # fmt: skip
SUPPORT_ALLOWED = ["/api/crm/contacts/", "/api/support/tickets/", "/api/genai/status/",
                   "/api/genai/conversations/"]  # fmt: skip
ADMIN_ONLY = ["/api/auth/users/", "/api/genai/usage/"]


@pytest.mark.parametrize("path", SALES_ONLY_LISTS)
def test_support_cannot_reach_sales_data(client_for, support_user, rep, path):
    assert client_for(support_user).get(path).status_code == 403
    assert client_for(rep).get(path).status_code == 200


@pytest.mark.parametrize("path", SUPPORT_ALLOWED)
def test_support_reaches_its_own_tools(client_for, support_user, path):
    assert client_for(support_user).get(path).status_code == 200


@pytest.mark.parametrize("path", ADMIN_ONLY)
def test_admin_only_endpoints(client_for, rep, admin_user, path):
    assert client_for(rep).get(path).status_code == 403
    assert client_for(admin_user).get(path).status_code == 200


@pytest.mark.parametrize(
    ("path", "method"),
    [("/api/ml/retrain/", "post"), ("/api/ml/rescore-all/", "post"),
     ("/api/auth/register/", "post"), ("/api/billing/payments/1/refund/", "post")],
)  # fmt: skip
def test_admin_only_actions(client_for, rep, path, method):
    assert getattr(client_for(rep), method)(path, {}, format="json").status_code == 403


def test_login_is_rate_limited(rep, settings):
    cache.clear()
    client = APIClient()
    codes = [
        client.post("/api/auth/login/", {"username": "rep1", "password": "wrong"},
                    format="json").status_code  # fmt: skip
        for _ in range(11)
    ]
    assert codes[:10] == [401] * 10 and codes[10] == 429
    cache.clear()
    ok = client.post("/api/auth/login/", {"username": "rep1", "password": PASSWORD}, format="json")
    assert ok.status_code == 200


def test_tokens_and_secrets_never_leak(client_for, rep, monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_ABC")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "super-secret-value")
    body = client_for(rep).get("/api/billing/config/").content.decode()
    assert "rzp_test_ABC" in body and "super-secret-value" not in body
    me = client_for(rep).get("/api/auth/me/").json()
    assert "password" not in me


def test_debug_is_off_outside_dev(settings):
    from config.settings import test as test_settings

    assert test_settings.DEBUG is False
