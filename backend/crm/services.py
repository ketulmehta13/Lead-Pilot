"""CRM business logic. Views stay thin and call these functions."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import IO, Any

from django.db import transaction
from django.db.models import Max, Q, QuerySet
from django.utils import timezone

from accounts.models import User

from .models import Activity, Company, Contact, Deal, Lead
from .serializers import ContactImportRowSerializer

# Activities that count as "we reached out to this contact".
CONTACTING_TYPES = {Activity.Type.CALL, Activity.Type.EMAIL, Activity.Type.MEETING}
OPEN_LEAD_STATUSES = [Lead.Status.NEW, Lead.Status.CONTACTED, Lead.Status.QUALIFIED]

CSV_MAX_BYTES = 2 * 1024 * 1024
CSV_MAX_ROWS = 5000
CSV_COLUMNS = {"first_name", "last_name", "email", "phone", "company", "tags"}
CSV_REQUIRED_COLUMNS = {"first_name", "email"}


class CsvImportError(ValueError):
    """The file itself is unusable (too big, wrong encoding, missing columns)."""


@dataclass
class ImportResult:
    total_rows: int = 0
    created: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"total_rows": self.total_rows, "created": self.created, "errors": self.errors}


def log_activity(*, owner: User, **data: Any) -> Activity:
    """Create an activity and, for calls/emails/meetings, stamp the contact's open leads.

    `last_contacted_at` only moves forward, so back-dating a note never "un-contacts" a lead.
    """
    activity = Activity.objects.create(owner=owner, **data)
    if activity.type in CONTACTING_TYPES:
        Lead.objects.filter(contact=activity.contact, status__in=OPEN_LEAD_STATUSES).filter(
            Q(last_contacted_at__isnull=True) | Q(last_contacted_at__lt=activity.occurred_at)
        ).update(last_contacted_at=activity.occurred_at)
        # A brand-new lead we've now reached becomes "contacted".
        Lead.objects.filter(contact=activity.contact, status=Lead.Status.NEW).update(
            status=Lead.Status.CONTACTED
        )
    return activity


def _parse_tags(raw: str) -> list[str]:
    parts = raw.replace("|", ";").replace(",", ";").split(";")
    return list(dict.fromkeys(p.strip().lower() for p in parts if p.strip()))


def _read_csv(upload: IO[bytes]) -> csv.DictReader:
    size = getattr(upload, "size", None)
    if size is not None and size > CSV_MAX_BYTES:
        raise CsvImportError("File is larger than 2 MB.")
    raw = upload.read(CSV_MAX_BYTES + 1)
    if len(raw) > CSV_MAX_BYTES:
        raise CsvImportError("File is larger than 2 MB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvImportError("File must be UTF-8 encoded CSV.") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise CsvImportError("File is empty.")
    reader.fieldnames = [(name or "").strip().lower() for name in reader.fieldnames]
    missing = CSV_REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        raise CsvImportError(f"Missing required column(s): {', '.join(sorted(missing))}.")
    return reader


def import_contacts_csv(upload: IO[bytes], owner: User) -> ImportResult:
    """Import contacts from a CSV file.

    Columns: first_name, email (required); last_name, phone, company, tags (optional).
    Tags are separated by ';' or '|'. Companies are matched by name among the owner's
    companies and created if missing.

    Valid rows are imported; invalid rows are skipped and reported as
    {"row": <line number in the file>, "errors": {field: [messages]}}.
    """
    reader = _read_csv(upload)
    result = ImportResult()
    valid: list[tuple[int, dict[str, Any]]] = []
    seen_emails: dict[str, int] = {}

    for index, row in enumerate(reader):
        line = index + 2  # header is line 1
        if index >= CSV_MAX_ROWS:
            raise CsvImportError(f"File has more than {CSV_MAX_ROWS} rows.")
        result.total_rows += 1
        data = {k: (v or "").strip() for k, v in row.items() if k in CSV_COLUMNS}
        serializer = ContactImportRowSerializer(data=data)
        if not serializer.is_valid():
            result.errors.append({"row": line, "errors": serializer.errors})
            continue
        email = serializer.validated_data["email"].lower()
        if email in seen_emails:
            result.errors.append(
                {"row": line, "errors": {"email": [f"Duplicate of row {seen_emails[email]}."]}}
            )
            continue
        seen_emails[email] = line
        valid.append((line, serializer.validated_data))

    existing = set(
        Contact.objects.filter(email__in=seen_emails.keys()).values_list("email", flat=True)
    )
    company_cache: dict[str, Company] = {}

    with transaction.atomic():
        for line, data in valid:
            email = data["email"].lower()
            if email in existing:
                message = "A contact with this email already exists."
                result.errors.append({"row": line, "errors": {"email": [message]}})
                continue
            company = None
            company_name = data.get("company", "")
            if company_name:
                key = company_name.lower()
                if key not in company_cache:
                    company_cache[key] = Company.objects.filter(
                        owner=owner, name__iexact=company_name
                    ).first() or Company.objects.create(owner=owner, name=company_name)
                company = company_cache[key]
            Contact.objects.create(
                owner=owner,
                first_name=data["first_name"],
                last_name=data.get("last_name", ""),
                email=email,
                phone=data.get("phone", ""),
                company=company,
                tags=_parse_tags(data.get("tags", "")),
            )
            result.created += 1

    result.errors.sort(key=lambda e: e["row"])
    return result


# --- Deals & pipeline ----------------------------------------------------------------------


class LeadAlreadyConverted(ValueError):
    """The lead already has a deal."""


def _next_position(stage: str) -> int:
    """Bottom of a Kanban column."""
    top = Deal.objects.filter(stage=stage).aggregate(m=Max("position"))["m"]
    return 0 if top is None else top + 1


def _enter_stage(deal: Deal, stage: str) -> None:
    """Set stage plus the fields that follow from it (probability, closed_at)."""
    deal.stage = stage
    deal.probability = Deal.DEFAULT_PROBABILITY[stage]
    deal.closed_at = timezone.now() if stage in Deal.CLOSED_STAGES else None


def _log_stage_change(deal: Deal, old_stage: str, actor: User) -> None:
    old = Deal.Stage(old_stage).label
    new = deal.get_stage_display()
    who = actor.get_full_name() or actor.username
    log_activity(
        owner=deal.owner or actor,  # owner keeps it on their contact timeline
        contact=deal.contact,
        deal=deal,
        type=Activity.Type.NOTE,
        subject=f"Deal moved to {new}",
        body=f'"{deal.title}" moved from {old} to {new} by {who}.',
    )


def create_deal(*, owner: User, **data: Any) -> Deal:
    """Create a deal at the bottom of its stage's column."""
    stage = data.pop("stage", Deal.Stage.NEW)
    probability = data.pop("probability", None)
    deal = Deal(owner=owner, **data)
    _enter_stage(deal, stage)
    if probability is not None:
        deal.probability = probability
    deal.position = _next_position(stage)
    deal.save()
    return deal


@transaction.atomic
def update_deal(deal: Deal, *, actor: User, **data: Any) -> Deal:
    """Edit a deal. A stage change moves it to the bottom of the new column."""
    new_stage = data.pop("stage", deal.stage)
    probability = data.pop("probability", None)
    for field_name, value in data.items():
        setattr(deal, field_name, value)
    old_stage = deal.stage
    if new_stage != old_stage:
        _enter_stage(deal, new_stage)
        deal.position = _next_position(new_stage)
    if probability is not None:
        deal.probability = probability
    deal.save()
    if new_stage != old_stage:
        _log_stage_change(deal, old_stage, actor)
    return deal


@transaction.atomic
def move_deal(
    deal: Deal, *, stage: str, position: int, actor: User, visible: QuerySet[Deal] | None = None
) -> Deal:
    """Move a deal to `stage` at `position` and renumber the column, atomically.

    `position` is the index among the deals the actor can *see* in that column (a rep only sees
    their own). It is translated into the shared column order, so other reps' cards keep their
    places. Rows are locked with SELECT ... FOR UPDATE (on Postgres) so concurrent drags can't
    interleave.
    """
    deal = Deal.objects.select_for_update().get(pk=deal.pk)
    column = list(
        Deal.objects.select_for_update()
        .filter(stage=stage)
        .exclude(pk=deal.pk)
        .order_by("position", "id")
    )
    if visible is None:
        visible_col = column
    else:
        visible_ids = set(visible.filter(stage=stage).values_list("id", flat=True))
        visible_col = [d for d in column if d.id in visible_ids]

    position = max(0, min(position, len(visible_col)))
    if position < len(visible_col):
        insert_at = column.index(visible_col[position])
    elif visible_col:
        insert_at = column.index(visible_col[-1]) + 1
    else:
        insert_at = len(column)
    column.insert(insert_at, deal)

    old_stage = deal.stage
    if stage != old_stage:
        _enter_stage(deal, stage)
    for index, item in enumerate(column):
        item.position = index
    Deal.objects.bulk_update([d for d in column if d.pk != deal.pk], ["position"])
    deal.save(update_fields=["stage", "probability", "closed_at", "position", "updated_at"])

    if stage != old_stage:
        _log_stage_change(deal, old_stage, actor)
    return deal


@transaction.atomic
def convert_lead(
    lead: Lead,
    *,
    title: str = "",
    value: Decimal | None = None,
    stage: str = Deal.Stage.QUALIFIED,
    expected_close_date: date | None = None,
) -> Deal:
    """Turn a lead into a deal and mark the lead converted (once only)."""
    lead = Lead.objects.select_for_update().select_related("contact__company").get(pk=lead.pk)
    if lead.status == Lead.Status.CONVERTED or Deal.objects.filter(lead=lead).exists():
        raise LeadAlreadyConverted("This lead has already been converted.")

    contact = lead.contact
    default_title = f"{contact.company.name if contact.company else contact.full_name} deal"
    deal = create_deal(
        owner=lead.owner,
        contact=contact,
        lead=lead,
        title=title or default_title,
        value=value if value is not None else (lead.budget or 0),
        stage=stage,
        expected_close_date=expected_close_date,
    )
    lead.status = Lead.Status.CONVERTED
    lead.save(update_fields=["status", "updated_at"])
    return deal


def board_columns(deals: QuerySet[Deal]) -> list[dict[str, Any]]:
    """Group deals into Kanban columns with count and total value."""
    by_stage: dict[str, list[Deal]] = {stage: [] for stage in Deal.Stage.values}
    for deal in deals.order_by("position", "id"):
        by_stage[deal.stage].append(deal)
    return [
        {
            "stage": stage,
            "label": Deal.Stage(stage).label,
            "count": len(items),
            "total_value": sum((d.value for d in items), Decimal("0")),
            "deals": items,
        }
        for stage, items in by_stage.items()
    ]
