"""crm.services: activity logging and CSV import."""

import io
import re
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import F
from django.utils import timezone

from billing.models import Invoice
from crm import services
from crm.models import Activity, Company, Contact, Deal, Lead, Task
from support.models import Ticket

pytestmark = pytest.mark.django_db


# --- log_activity -------------------------------------------------------------------------


def test_call_stamps_open_leads_and_marks_new_as_contacted(rep, lead_of, contact_of):
    contact = contact_of(rep)
    new_lead = lead_of(rep, contact=contact)
    converted = lead_of(rep, contact=contact, status=Lead.Status.CONVERTED)

    activity = services.log_activity(owner=rep, contact=contact, type="call", subject="Hi")

    new_lead.refresh_from_db()
    converted.refresh_from_db()
    assert new_lead.last_contacted_at == activity.occurred_at
    assert new_lead.status == Lead.Status.CONTACTED
    assert converted.last_contacted_at is None  # closed leads are left alone


def test_note_does_not_count_as_contact(rep, lead_of):
    lead = lead_of(rep)
    services.log_activity(owner=rep, contact=lead.contact, type="note", subject="Thought")
    lead.refresh_from_db()
    assert lead.last_contacted_at is None and lead.status == Lead.Status.NEW


def test_backdated_activity_never_moves_last_contacted_backwards(rep, lead_of):
    lead = lead_of(rep)
    recent = services.log_activity(owner=rep, contact=lead.contact, type="email", subject="A")
    services.log_activity(
        owner=rep, contact=lead.contact, type="call", subject="B",
        occurred_at=timezone.now() - timedelta(days=30),
    )  # fmt: skip
    lead.refresh_from_db()
    assert lead.last_contacted_at == recent.occurred_at


# --- CSV import --------------------------------------------------------------------------


def csv_file(text: str, name: str = "contacts.csv") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, text.encode("utf-8"), content_type="text/csv")


def test_import_20_rows_with_errors_reported_per_row(client_for, rep, contact_of):
    contact_of(rep, email="taken@x.io")
    rows = [f"Person{i},Last{i},person{i}@x.io,98765{i:05d},Initech,vip;trial" for i in range(17)]
    rows += [
        ",NoFirst,nofirst@x.io,,,",  # missing first name
        "Bad,Email,not-an-email,,,",  # invalid email
        "Dup,Row,person0@x.io,,,",  # duplicate of row 2 inside the file
    ]
    rows.insert(5, "Old,Contact,TAKEN@x.io,,,")  # already in DB (case-insensitive)
    text = "first_name,last_name,email,phone,company,tags\n" + "\n".join(rows)

    response = client_for(rep).post(
        "/api/crm/contacts/import/", {"file": csv_file(text)}, format="multipart"
    )
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["total_rows"] == 21
    assert body["created"] == 17
    # Header is line 1, so data rows are lines 2..22.
    assert [e["row"] for e in body["errors"]] == [7, 20, 21, 22]
    assert "first_name" in body["errors"][1]["errors"]
    assert "email" in body["errors"][2]["errors"]
    assert "Duplicate of row 2" in body["errors"][3]["errors"]["email"][0]
    assert "already exists" in body["errors"][0]["errors"]["email"][0]

    imported = Contact.objects.get(email="person3@x.io")
    assert imported.owner == rep and imported.tags == ["vip", "trial"]
    # All rows share one company, created once and owned by the importer.
    assert Company.objects.filter(name="Initech", owner=rep).count() == 1
    assert imported.company.name == "Initech"


def test_import_reuses_existing_company_case_insensitively(rep):
    existing = Company.objects.create(owner=rep, name="Umbrella Corp")
    text = "first_name,email,company\nAnu,anu@x.io,umbrella corp\n"
    result = services.import_contacts_csv(io.BytesIO(text.encode()), owner=rep)
    assert result.created == 1
    assert Contact.objects.get(email="anu@x.io").company == existing


def test_import_handles_bom_and_header_case(rep):
    text = "﻿First_Name , EMAIL\nZoya,zoya@x.io\n"
    result = services.import_contacts_csv(io.BytesIO(text.encode("utf-8")), owner=rep)
    assert result.created == 1 and result.errors == []


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("name,phone\nA,1\n", "Missing required column(s): email, first_name."),
        ("", "File is empty."),
    ],
)
def test_import_rejects_unusable_files(rep, content, message):
    with pytest.raises(services.CsvImportError, match=re.escape(message)):
        services.import_contacts_csv(io.BytesIO(content.encode()), owner=rep)


def test_import_rejects_non_utf8(rep):
    data = "first_name,email\nJosé,j@x.io".encode("cp1252")
    with pytest.raises(services.CsvImportError, match="UTF-8"):
        services.import_contacts_csv(io.BytesIO(data), rep)


def test_import_endpoint_validates_upload(client_for, rep):
    client = client_for(rep)
    missing = client.post("/api/crm/contacts/import/", {}, format="multipart")
    assert missing.status_code == 400
    wrong_type = client.post(
        "/api/crm/contacts/import/", {"file": csv_file("x", name="data.xlsx")}, format="multipart"
    )
    assert wrong_type.status_code == 400
    bad_header = client.post(
        "/api/crm/contacts/import/", {"file": csv_file("foo\n1\n")}, format="multipart"
    )
    assert bad_header.status_code == 400
    assert "Missing required column" in bad_header.json()["error"]["details"]["file"][0]


# --- seed_demo ---------------------------------------------------------------------------


def test_seed_demo_creates_expected_volumes(db):
    call_command("seed_demo", stdout=io.StringIO())
    assert Company.objects.count() == 50
    assert Contact.objects.count() == 300
    assert Lead.objects.count() == 400
    assert Activity.objects.count() == 500
    assert Task.objects.count() == 120
    # 150 pipeline deals + 240 closed deals of history for forecasting/RFM.
    assert Deal.objects.count() == 390
    assert Deal.objects.filter(stage__in=["won", "lost"], closed_at__isnull=True).count() == 0
    assert Ticket.objects.count() == 80
    assert Invoice.objects.exists() and Invoice.objects.filter(status="paid").exists()
    # Every converted lead has exactly one deal.
    assert not Lead.objects.filter(status="converted", deal__isnull=True).exists()
    # Every contact belongs to the same rep as its company (keeps owner scoping coherent).
    assert not Contact.objects.exclude(company=None).exclude(owner=F("company__owner"))


def test_seed_demo_refuses_to_run_twice_without_flush(db):
    call_command("seed_demo", stdout=io.StringIO())
    with pytest.raises(CommandError):
        call_command("seed_demo", stdout=io.StringIO())
    call_command("seed_demo", "--flush", stdout=io.StringIO())
    assert Contact.objects.count() == 300


def test_seed_demo_small_size_is_lighter_but_complete(db):
    call_command("seed_demo", "--size", "small", stdout=io.StringIO())
    assert Company.objects.count() == 12
    assert Contact.objects.count() == 40
    assert Lead.objects.count() == 50
    assert Activity.objects.count() == 120
    assert Task.objects.count() == 20
    assert Ticket.objects.count() == 15
    assert Deal.objects.count() == 24 + 72
    # Still enough history for the forecast (>= 15 months) and some invoices to show.
    months = {d.closed_at.strftime("%Y-%m") for d in Deal.objects.filter(stage="won")}
    assert len(months) >= 15
    assert Invoice.objects.exists()
    assert not Lead.objects.filter(status="converted", deal__isnull=True).exists()


def test_seed_demo_minimal_is_two_of_each_and_pages_still_work(db, client_for):
    call_command("seed_demo", "--size", "small", stdout=io.StringIO())
    call_command("seed_demo", "--flush", "--size", "minimal", stdout=io.StringIO())
    assert Company.objects.count() == 2
    assert Contact.objects.count() == 2
    assert Lead.objects.count() == 2
    assert Activity.objects.count() == 2
    assert Deal.objects.count() == 2
    assert Task.objects.count() == 2
    assert Ticket.objects.count() == 2
    assert not Lead.objects.filter(status="converted", deal__isnull=True).exists()

    from accounts.models import User

    admin = User.objects.get(username="admin")
    client = client_for(admin)
    # Dashboard, forecast and segments cope with almost no data.
    for path in ("/api/analytics/summary/", "/api/ml/forecast/", "/api/ml/segments/"):
        assert client.get(path).status_code == 200, path


def test_seed_demo_if_empty_skips_existing_data(db):
    """Used on every free-plan start: must never fail or duplicate data."""
    call_command("seed_demo", "--if-empty", stdout=io.StringIO())
    assert Contact.objects.count() == 300
    out = io.StringIO()
    call_command("seed_demo", "--if-empty", stdout=out)
    assert "skipping" in out.getvalue()
    assert Contact.objects.count() == 300
