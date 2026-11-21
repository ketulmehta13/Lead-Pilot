import pytest
from django.urls import reverse

from accounts.models import User
from conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_login_returns_tokens_and_user(client_for, rep):
    response = client_for(None).post(
        reverse("login"), {"username": "rep1", "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access"] and body["refresh"]
    assert body["user"]["role"] == "sales"


def test_login_with_wrong_password_is_rejected(client_for, rep):
    response = client_for(None).post(
        reverse("login"), {"username": "rep1", "password": "nope"}, format="json"
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "no_active_account"


def test_refresh_issues_new_access_token(client_for, rep):
    login = (
        client_for(None)
        .post(reverse("login"), {"username": "rep1", "password": PASSWORD}, format="json")
        .json()
    )
    response = client_for(None).post(
        reverse("token-refresh"), {"refresh": login["refresh"]}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["access"]


def test_me_requires_auth_and_returns_user(client_for, rep):
    assert client_for(None).get(reverse("me")).status_code == 401
    response = client_for(rep).get(reverse("me"))
    assert response.status_code == 200
    assert response.json()["username"] == "rep1"


def test_jwt_bearer_header_authenticates(client_for, rep):
    login = (
        client_for(None)
        .post(reverse("login"), {"username": "rep1", "password": PASSWORD}, format="json")
        .json()
    )
    client = client_for(None)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    assert client.get(reverse("me")).status_code == 200


@pytest.mark.parametrize("who", ["rep", "support_user", None])
def test_only_admin_can_register(client_for, request, who):
    user = request.getfixturevalue(who) if who else None
    payload = {"username": "new", "email": "new@x.io", "password": "Sup3r-secret!", "role": "sales"}
    response = client_for(user).post(reverse("register"), payload, format="json")
    assert response.status_code == (401 if user is None else 403)
    assert not User.objects.filter(username="new").exists()


def test_admin_registers_user(client_for, admin_user):
    payload = {
        "username": "newrep", "email": "NewRep@x.io", "password": "Sup3r-secret!",
        "role": "support", "first_name": "New",
    }  # fmt: skip
    response = client_for(admin_user).post(reverse("register"), payload, format="json")
    assert response.status_code == 201
    user = User.objects.get(username="newrep")
    assert user.role == "support" and user.email == "newrep@x.io"
    assert user.check_password("Sup3r-secret!")
    assert "password" not in response.json()


def test_register_rejects_weak_password(client_for, admin_user):
    payload = {"username": "weak", "email": "weak@x.io", "password": "123", "role": "sales"}
    response = client_for(admin_user).post(reverse("register"), payload, format="json")
    assert response.status_code == 400
    assert "password" in response.json()["error"]["details"]


def test_superuser_is_always_admin(db):
    user = User.objects.create_superuser("root", "root@x.io", PASSWORD)
    assert user.role == User.Role.ADMIN


def test_user_list_is_admin_only(client_for, admin_user, rep):
    assert client_for(rep).get("/api/auth/users/").status_code == 403
    response = client_for(admin_user).get("/api/auth/users/")
    assert response.status_code == 200
    assert response.json()["count"] == 2
