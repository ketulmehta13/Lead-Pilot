import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_returns_ok() -> None:
    response = APIClient().get(reverse("health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_swagger_docs_load() -> None:
    client = APIClient()
    assert client.get(reverse("schema")).status_code == 200
    assert client.get(reverse("swagger-ui")).status_code == 200


@pytest.mark.django_db
def test_protected_endpoints_require_auth_by_default() -> None:
    from rest_framework.decorators import api_view
    from rest_framework.response import Response
    from rest_framework.test import APIRequestFactory

    @api_view(["GET"])
    def secret(request):  # noqa: ANN001
        return Response({"ok": True})

    response = secret(APIRequestFactory().get("/x/"))
    assert response.status_code == 401
    assert response.data["error"]["code"] == "not_authenticated"
