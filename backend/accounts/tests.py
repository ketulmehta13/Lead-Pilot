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
    rep.refresh_from_db()
    assert rep.last_login is not None  # shown as "Last sign-in" in Settings > Team


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


# --- Settings: profile, password, team management -------------------------------------------

NEW_PASSWORD = "Sunrise-Ledger-42"


def test_user_can_update_own_profile(client_for, rep):
    response = client_for(rep).patch(
        reverse("me"), {"first_name": "Riya", "email": "Riya@Example.com"}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Riya"
    rep.refresh_from_db()
    assert rep.email == "riya@example.com"


def test_profile_email_must_be_unique(client_for, rep, admin_user):
    response = client_for(rep).patch(reverse("me"), {"email": admin_user.email}, format="json")
    assert response.status_code == 400
    assert "email" in response.json()["error"]["details"]


def test_change_password_requires_current_password(client_for, rep):
    bad = client_for(rep).post(
        reverse("change-password"),
        {"current_password": "wrong", "new_password": NEW_PASSWORD},
        format="json",
    )
    assert bad.status_code == 400
    assert "current_password" in bad.json()["error"]["details"]

    weak = client_for(rep).post(
        reverse("change-password"),
        {"current_password": PASSWORD, "new_password": "123"},
        format="json",
    )
    assert weak.status_code == 400
    assert "new_password" in weak.json()["error"]["details"]

    ok = client_for(rep).post(
        reverse("change-password"),
        {"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        format="json",
    )
    assert ok.status_code == 204
    rep.refresh_from_db()
    assert rep.check_password(NEW_PASSWORD)


def test_admin_changes_role_and_deactivates_a_user(client_for, admin_user, rep):
    url = reverse("user-detail", args=[rep.pk])
    response = client_for(admin_user).patch(url, {"role": "support"}, format="json")
    assert response.status_code == 200 and response.json()["role"] == "support"

    response = client_for(admin_user).patch(url, {"is_active": False}, format="json")
    assert response.status_code == 200 and response.json()["is_active"] is False
    # Hidden from the default list (task assignment), shown in Settings > Team.
    listed = client_for(admin_user).get(reverse("user-list")).json()["results"]
    assert rep.pk not in [u["id"] for u in listed]
    everyone = client_for(admin_user).get(reverse("user-list"), {"include_inactive": "true"})
    assert rep.pk in [u["id"] for u in everyone.json()["results"]]
    # A deactivated user can't log in.
    login = client_for(None).post(
        reverse("login"), {"username": rep.username, "password": PASSWORD}, format="json"
    )
    assert login.status_code == 401


def test_admin_cannot_lock_themselves_out(client_for, admin_user):
    url = reverse("user-detail", args=[admin_user.pk])
    demote = client_for(admin_user).patch(url, {"role": "sales"}, format="json")
    assert demote.status_code == 400
    deactivate = client_for(admin_user).patch(url, {"is_active": False}, format="json")
    assert deactivate.status_code == 400
    admin_user.refresh_from_db()
    assert admin_user.is_admin and admin_user.is_active


def test_last_active_admin_cannot_be_demoted(client_for, admin_user):
    other = User.objects.create_user("boss2", "boss2@example.com", PASSWORD, role="admin")
    url = reverse("user-detail", args=[admin_user.pk])
    # boss2 may demote admin_user while another admin (boss2) remains...
    assert client_for(other).patch(url, {"role": "sales"}, format="json").status_code == 200
    # ...but then boss2 is the last admin and can't be demoted by anyone.
    other_url = reverse("user-detail", args=[other.pk])
    admin_user.role = "admin"
    admin_user.save()
    admin_user.refresh_from_db()
    User.objects.filter(pk=admin_user.pk).update(is_active=False)
    response = client_for(other).patch(other_url, {"role": "sales"}, format="json")
    assert response.status_code == 400


def test_admin_resets_a_password(client_for, admin_user, rep):
    url = reverse("user-set-password", args=[rep.pk])
    assert client_for(admin_user).post(url, {"password": "x"}, format="json").status_code == 400
    response = client_for(admin_user).post(url, {"password": NEW_PASSWORD}, format="json")
    assert response.status_code == 204
    rep.refresh_from_db()
    assert rep.check_password(NEW_PASSWORD)


@pytest.mark.parametrize("who", ["rep", "support_user"])
def test_only_admins_manage_the_team(client_for, request, who, admin_user):
    user = request.getfixturevalue(who)
    client = client_for(user)
    detail = reverse("user-detail", args=[admin_user.pk])
    assert client.patch(detail, {"role": "sales"}, format="json").status_code == 403
    reset = reverse("user-set-password", args=[admin_user.pk])
    assert client.post(reset, {"password": NEW_PASSWORD}, format="json").status_code == 403
