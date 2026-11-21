"""Deals, the Kanban move endpoint and lead conversion."""

from decimal import Decimal

import pytest

from crm import services
from crm.models import Activity, Deal, Lead

pytestmark = pytest.mark.django_db


@pytest.fixture
def deal_of(contact_of):
    """deal_of(user, stage="new", **fields) -> Deal placed at the bottom of its column."""

    def _make(user, stage=Deal.Stage.NEW, **fields):
        contact = fields.pop("contact", None) or contact_of(user)
        return services.create_deal(
            owner=user, contact=contact, title=fields.pop("title", "Deal"), stage=stage, **fields
        )

    return _make


def column(stage):
    return list(Deal.objects.filter(stage=stage).order_by("position", "id"))


# --- CRUD + permissions -------------------------------------------------------------------


def test_create_deal_appends_to_column_with_stage_defaults(client_for, rep, contact_of, deal_of):
    first = deal_of(rep, stage="proposal")
    response = client_for(rep).post(
        "/api/crm/deals/",
        {"title": "Big one", "contact": contact_of(rep).id, "value": "50000", "stage": "proposal"},
        format="json",
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["position"] == first.position + 1
    assert body["probability"] == 50
    assert body["closed_at"] is None


def test_rep_cannot_see_or_move_another_reps_deal(client_for, rep, other_rep, deal_of):
    theirs = deal_of(other_rep)
    client = client_for(rep)
    assert client.get("/api/crm/deals/").json()["count"] == 0
    response = client.post(
        f"/api/crm/deals/{theirs.id}/move/", {"stage": "won", "position": 0}, format="json"
    )
    assert response.status_code == 404
    theirs.refresh_from_db()
    assert theirs.stage == "new"


def test_support_cannot_use_deals(client_for, support_user):
    assert client_for(support_user).get("/api/crm/deals/").status_code == 403


def test_deal_value_cannot_be_negative(client_for, rep, contact_of):
    response = client_for(rep).post(
        "/api/crm/deals/",
        {"title": "X", "contact": contact_of(rep).id, "value": "-1"},
        format="json",
    )
    assert response.status_code == 400


def test_editing_stage_via_patch_moves_to_bottom_and_logs(client_for, rep, deal_of):
    deal_of(rep, stage="won")
    deal = deal_of(rep, stage="new")
    response = client_for(rep).patch(f"/api/crm/deals/{deal.id}/", {"stage": "won"}, format="json")
    assert response.status_code == 200
    deal.refresh_from_db()
    assert deal.stage == "won" and deal.position == 1 and deal.closed_at is not None
    assert Activity.objects.filter(deal=deal, subject="Deal moved to Won").exists()


# --- move_deal ----------------------------------------------------------------------------


def test_move_within_column_reorders(client_for, rep, deal_of):
    a, b, c = (deal_of(rep, title=t) for t in "abc")
    response = client_for(rep).post(
        f"/api/crm/deals/{c.id}/move/", {"stage": "new", "position": 0}, format="json"
    )
    assert response.status_code == 200
    assert [d.title for d in column("new")] == ["c", "a", "b"]
    assert [d.position for d in column("new")] == [0, 1, 2]
    assert not Activity.objects.exists()  # same stage: no timeline note


def test_move_across_columns_sets_stage_fields_and_persists(client_for, rep, deal_of):
    moving = deal_of(rep, title="moving")
    deal_of(rep, stage="won", title="w1")
    deal_of(rep, stage="won", title="w2")
    client_for(rep).post(
        f"/api/crm/deals/{moving.id}/move/", {"stage": "won", "position": 1}, format="json"
    )
    # A fresh read from the DB (what a page refresh does) keeps the new place.
    assert [d.title for d in column("won")] == ["w1", "moving", "w2"]
    moving.refresh_from_db()
    assert moving.probability == 100 and moving.closed_at is not None
    note = Activity.objects.get(deal=moving)
    assert note.type == "note" and "from New to Won" in note.body


def test_moving_out_of_won_clears_closed_at(rep, deal_of):
    deal = deal_of(rep, stage="won")
    services.move_deal(deal, stage="negotiation", position=0, actor=rep)
    deal.refresh_from_db()
    assert deal.closed_at is None and deal.probability == 75


def test_position_is_clamped(rep, deal_of):
    a = deal_of(rep, title="a")
    b = deal_of(rep, title="b")
    services.move_deal(a, stage="new", position=99, actor=rep)
    assert [d.title for d in column("new")] == ["b", "a"]
    assert b  # noqa: B018


def test_rep_index_is_translated_around_hidden_deals(rep, other_rep, deal_of):
    """Rep sees [r1, r2]; other rep's o1 sits between them. Dropping at index 1 (before r2)
    must land right before r2, not before o1."""
    deal_of(rep, title="r1")
    deal_of(other_rep, title="o1")
    deal_of(rep, title="r2")
    moving = deal_of(rep, stage="proposal", title="m")
    visible = Deal.objects.filter(owner=rep)
    services.move_deal(moving, stage="new", position=1, actor=rep, visible=visible)
    assert [d.title for d in column("new")] == ["r1", "o1", "m", "r2"]


def test_drop_at_end_of_reps_visible_column(rep, other_rep, deal_of):
    deal_of(rep, title="r1")
    deal_of(other_rep, title="o1")
    moving = deal_of(rep, stage="lost", title="m")
    visible = Deal.objects.filter(owner=rep)
    services.move_deal(moving, stage="new", position=5, actor=rep, visible=visible)
    assert [d.title for d in column("new")] == ["r1", "m", "o1"]


def test_board_groups_columns_with_totals(client_for, rep, deal_of):
    deal_of(rep, stage="new", value=Decimal("100"))
    deal_of(rep, stage="new", value=Decimal("250.50"))
    deal_of(rep, stage="won", value=Decimal("1000"))
    board = client_for(rep).get("/api/crm/deals/board/").json()
    assert [c["stage"] for c in board] == list(Deal.Stage.values)
    new = board[0]
    assert new["count"] == 2 and Decimal(new["total_value"]) == Decimal("350.50")
    assert [c["count"] for c in board] == [2, 0, 0, 0, 1, 0]


def test_board_respects_search(client_for, rep, deal_of):
    deal_of(rep, title="Acme renewal")
    deal_of(rep, title="Globex pilot")
    board = client_for(rep).get("/api/crm/deals/board/", {"search": "renewal"}).json()
    assert sum(c["count"] for c in board) == 1


def test_move_rejects_unknown_stage(client_for, rep, deal_of):
    deal = deal_of(rep)
    response = client_for(rep).post(
        f"/api/crm/deals/{deal.id}/move/", {"stage": "maybe", "position": 0}, format="json"
    )
    assert response.status_code == 400


# --- convert lead -------------------------------------------------------------------------


def test_convert_lead_creates_deal_and_marks_converted(client_for, rep, lead_of):
    lead = lead_of(rep, budget=Decimal("75000"), status="qualified")
    response = client_for(rep).post(f"/api/crm/leads/{lead.id}/convert/", {}, format="json")
    assert response.status_code == 201, response.json()
    deal = Deal.objects.get(lead=lead)
    assert response.json()["id"] == deal.id
    assert deal.value == Decimal("75000") and deal.stage == "qualified"
    assert deal.owner == rep and deal.contact == lead.contact
    assert deal.title == f"{lead.contact.company.name} deal"
    lead.refresh_from_db()
    assert lead.status == Lead.Status.CONVERTED
    assert client_for(rep).get(f"/api/crm/leads/{lead.id}/").json()["deal"] == deal.id


def test_convert_with_custom_values(client_for, rep, lead_of):
    lead = lead_of(rep)
    response = client_for(rep).post(
        f"/api/crm/leads/{lead.id}/convert/",
        {"title": "Custom", "value": "1200", "stage": "proposal"},
        format="json",
    )
    assert response.json()["title"] == "Custom" and response.json()["stage"] == "proposal"


def test_lead_can_only_be_converted_once(client_for, rep, lead_of):
    lead = lead_of(rep)
    client = client_for(rep)
    assert client.post(f"/api/crm/leads/{lead.id}/convert/", {}).status_code == 201
    second = client.post(f"/api/crm/leads/{lead.id}/convert/", {})
    assert second.status_code == 400
    assert "already been converted" in second.json()["error"]["message"]
    assert Deal.objects.count() == 1


def test_convert_cannot_start_closed(client_for, rep, lead_of):
    lead = lead_of(rep)
    response = client_for(rep).post(
        f"/api/crm/leads/{lead.id}/convert/", {"stage": "won"}, format="json"
    )
    assert response.status_code == 400


def test_rep_cannot_convert_another_reps_lead(client_for, rep, other_rep, lead_of):
    lead = lead_of(other_rep)
    assert client_for(rep).post(f"/api/crm/leads/{lead.id}/convert/", {}).status_code == 404
