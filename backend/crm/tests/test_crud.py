"""CRUD, search, filters and validation for CRM endpoints."""

from datetime import timedelta

import pytest
from django.utils import timezone

from crm.models import Company, Contact, Lead, Task

pytestmark = pytest.mark.django_db


def test_company_crud(client_for, rep):
    client = client_for(rep)
    created = client.post(
        "/api/crm/companies/",
        {"name": "Globex", "industry": "technology", "size": "11-50", "city": "Pune"},
        format="json",
    )
    assert created.status_code == 201
    company_id = created.json()["id"]
    assert created.json()["owner"] == rep.id

    updated = client.patch(f"/api/crm/companies/{company_id}/", {"city": "Mumbai"}, format="json")
    assert updated.json()["city"] == "Mumbai"

    assert client.delete(f"/api/crm/companies/{company_id}/").status_code == 204
    assert not Company.objects.exists()


def test_contact_create_normalises_email_and_tags(client_for, rep):
    response = client_for(rep).post(
        "/api/crm/contacts/",
        {"first_name": "Ravi", "email": " Ravi@Example.COM ", "tags": ["VIP", " vip", "Trial"]},
        format="json",
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["email"] == "ravi@example.com"
    assert body["tags"] == ["vip", "trial"]
    assert body["full_name"] == "Ravi"


def test_contact_email_must_be_unique_ignoring_case(client_for, rep, contact_of):
    contact_of(rep, email="dup@x.io")
    response = client_for(rep).post(
        "/api/crm/contacts/", {"first_name": "A", "email": "DUP@x.io"}, format="json"
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid"
    assert "email" in response.json()["error"]["details"]


def test_contact_update_keeps_own_email(client_for, rep, contact_of):
    contact = contact_of(rep, email="me@x.io")
    response = client_for(rep).patch(
        f"/api/crm/contacts/{contact.id}/", {"email": "ME@x.io", "phone": "123"}, format="json"
    )
    assert response.status_code == 200


def test_ml_fields_are_read_only(client_for, rep, lead_of):
    lead = lead_of(rep)
    client_for(rep).patch(
        f"/api/crm/leads/{lead.id}/", {"score": 99, "score_label": "hot"}, format="json"
    )
    lead.refresh_from_db()
    assert lead.score is None and lead.score_label is None


def test_contact_search_and_filters(client_for, rep, contact_of):
    a = contact_of(rep, first_name="Meera", email="meera@x.io", tags=["vip"])
    contact_of(rep, first_name="Karan", email="karan@x.io", tags=["vip-old"])
    client = client_for(rep)

    found = client.get("/api/crm/contacts/", {"search": "meer"}).json()["results"]
    assert [c["id"] for c in found] == [a.id]

    tagged = client.get("/api/crm/contacts/", {"tag": "VIP"}).json()["results"]
    assert [c["id"] for c in tagged] == [a.id]

    by_company = client.get("/api/crm/contacts/", {"company": a.company_id}).json()["results"]
    assert [c["id"] for c in by_company] == [a.id]


def test_lead_filters_and_ordering(client_for, rep, lead_of):
    small = lead_of(rep, status="new", budget=1000)
    big = lead_of(rep, status="qualified", budget=50000)
    client = client_for(rep)

    qualified = client.get("/api/crm/leads/", {"status": "qualified"}).json()["results"]
    assert [lead["id"] for lead in qualified] == [big.id]

    rich = client.get("/api/crm/leads/", {"budget_min": 10000}).json()["results"]
    assert [lead["id"] for lead in rich] == [big.id]

    ordered = client.get("/api/crm/leads/", {"ordering": "budget"}).json()["results"]
    assert [lead["id"] for lead in ordered] == [small.id, big.id]


def test_lead_rejects_negative_budget(client_for, rep, contact_of):
    response = client_for(rep).post(
        "/api/crm/leads/", {"contact": contact_of(rep).id, "budget": "-5"}, format="json"
    )
    assert response.status_code == 400


def test_list_is_paginated(client_for, rep):
    Company.objects.bulk_create(Company(owner=rep, name=f"C{i}") for i in range(25))
    first = client_for(rep).get("/api/crm/companies/").json()
    assert first["count"] == 25 and len(first["results"]) == 20 and first["next"]
    big_page = client_for(rep).get("/api/crm/companies/", {"page_size": 50}).json()
    assert len(big_page["results"]) == 25


def test_company_reports_contact_count(client_for, rep, contact_of):
    contact = contact_of(rep)
    Contact.objects.create(owner=rep, first_name="B", email="b@x.io", company=contact.company)
    row = client_for(rep).get(f"/api/crm/companies/{contact.company_id}/").json()
    assert row["contact_count"] == 2


def test_task_defaults_to_creator_and_can_be_completed(client_for, rep):
    client = client_for(rep)
    created = client.post("/api/crm/tasks/", {"title": "Call Asha"}, format="json").json()
    assert created["assigned_to"] == rep.id and created["status"] == "todo"
    done = client.patch(f"/api/crm/tasks/{created['id']}/", {"status": "done"}, format="json")
    assert done.json()["status"] == "done"


def test_timeline_lists_contact_activities_newest_first(client_for, rep, contact_of):
    contact = contact_of(rep)
    client = client_for(rep)
    old = timezone.now() - timedelta(days=3)
    client.post(
        "/api/crm/activities/",
        {"contact": contact.id, "type": "note", "subject": "Old", "occurred_at": old.isoformat()},
        format="json",
    )
    client.post(
        "/api/crm/activities/",
        {"contact": contact.id, "type": "call", "subject": "New"},
        format="json",
    )
    rows = client.get("/api/crm/activities/", {"contact": contact.id}).json()["results"]
    assert [r["subject"] for r in rows] == ["New", "Old"]


def test_unknown_lead_returns_consistent_404(client_for, rep):
    response = client_for(rep).get("/api/crm/leads/999/")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_deleting_contact_removes_its_leads(client_for, rep, lead_of):
    lead = lead_of(rep)
    client_for(rep).delete(f"/api/crm/contacts/{lead.contact_id}/")
    assert not Lead.objects.exists()


def test_task_open_filter_excludes_done(client_for, rep):
    Task.objects.create(owner=rep, assigned_to=rep, title="Open", status="todo")
    Task.objects.create(owner=rep, assigned_to=rep, title="Doing", status="in_progress")
    Task.objects.create(owner=rep, assigned_to=rep, title="Finished", status="done")
    client = client_for(rep)
    open_titles = {
        t["title"] for t in client.get("/api/crm/tasks/", {"open": "true"}).json()["results"]
    }
    assert open_titles == {"Open", "Doing"}
    done = client.get("/api/crm/tasks/", {"open": "false"}).json()["results"]
    assert [t["title"] for t in done] == ["Finished"]
