"""Role + ownership rules for every CRM endpoint."""

import pytest

from crm.models import Activity, Contact, Lead, Task

pytestmark = pytest.mark.django_db

ENDPOINTS = ["companies", "contacts", "leads", "activities", "tasks"]


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_anonymous_is_rejected(client_for, endpoint):
    assert client_for(None).get(f"/api/crm/{endpoint}/").status_code == 401


def test_sales_rep_cannot_see_another_reps_leads(client_for, rep, other_rep, lead_of):
    mine = lead_of(rep)
    theirs = lead_of(other_rep)

    response = client_for(rep).get("/api/crm/leads/")
    ids = [row["id"] for row in response.json()["results"]]
    assert ids == [mine.id]

    # Direct access to another rep's lead looks like it doesn't exist.
    assert client_for(rep).get(f"/api/crm/leads/{theirs.id}/").status_code == 404
    assert (
        client_for(rep)
        .patch(f"/api/crm/leads/{theirs.id}/", {"status": "qualified"}, format="json")
        .status_code
        == 404
    )
    assert client_for(rep).delete(f"/api/crm/leads/{theirs.id}/").status_code == 404
    theirs.refresh_from_db()
    assert theirs.status == Lead.Status.NEW


def test_admin_sees_every_reps_leads(client_for, admin_user, rep, other_rep, lead_of):
    lead_of(rep)
    lead_of(other_rep)
    assert client_for(admin_user).get("/api/crm/leads/").json()["count"] == 2


def test_rep_cannot_attach_lead_to_another_reps_contact(client_for, rep, other_rep, contact_of):
    their_contact = contact_of(other_rep)
    response = client_for(rep).post(
        "/api/crm/leads/", {"contact": their_contact.id, "source": "web"}, format="json"
    )
    assert response.status_code == 400
    assert "contact" in response.json()["error"]["details"]
    assert not Lead.objects.exists()


def test_rep_cannot_log_activity_on_another_reps_contact(client_for, rep, other_rep, contact_of):
    their_contact = contact_of(other_rep)
    response = client_for(rep).post(
        "/api/crm/activities/",
        {"contact": their_contact.id, "type": "call", "subject": "Hi"},
        format="json",
    )
    assert response.status_code == 400
    assert not Activity.objects.exists()


def test_support_reads_all_contacts_but_cannot_write(
    client_for, support_user, rep, other_rep, contact_of
):
    contact = contact_of(rep)
    contact_of(other_rep)
    client = client_for(support_user)

    assert client.get("/api/crm/contacts/").json()["count"] == 2
    assert client.get(f"/api/crm/contacts/{contact.id}/").status_code == 200
    assert (
        client.patch(
            f"/api/crm/contacts/{contact.id}/", {"first_name": "X"}, format="json"
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/crm/contacts/", {"first_name": "X", "email": "x@x.io"}, format="json"
        ).status_code
        == 403
    )
    assert client.delete(f"/api/crm/contacts/{contact.id}/").status_code == 403
    assert Contact.objects.count() == 2


@pytest.mark.parametrize("endpoint", ["companies", "leads", "activities", "tasks"])
def test_support_has_no_access_to_sales_data(client_for, support_user, endpoint):
    assert client_for(support_user).get(f"/api/crm/{endpoint}/").status_code == 403


def test_support_cannot_import_contacts(client_for, support_user):
    assert client_for(support_user).post("/api/crm/contacts/import/").status_code == 403


def test_rep_sees_tasks_assigned_to_them(client_for, admin_user, rep, other_rep):
    Task.objects.create(owner=admin_user, assigned_to=rep, title="From admin")
    Task.objects.create(owner=rep, assigned_to=rep, title="Mine")
    Task.objects.create(owner=other_rep, assigned_to=other_rep, title="Not mine")
    titles = {t["title"] for t in client_for(rep).get("/api/crm/tasks/").json()["results"]}
    assert titles == {"From admin", "Mine"}


def test_rep_cannot_assign_task_to_someone_else(client_for, rep, other_rep):
    response = client_for(rep).post(
        "/api/crm/tasks/", {"title": "Do it", "assigned_to": other_rep.id}, format="json"
    )
    assert response.status_code == 400
    assert "assigned_to" in response.json()["error"]["details"]


def test_admin_can_assign_task_to_anyone(client_for, admin_user, rep):
    response = client_for(admin_user).post(
        "/api/crm/tasks/", {"title": "Do it", "assigned_to": rep.id}, format="json"
    )
    assert response.status_code == 201
    assert response.json()["assigned_to"] == rep.id
