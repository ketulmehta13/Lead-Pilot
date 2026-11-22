"""Fill the database with realistic demo data.

    python manage.py seed_demo            # refuses if CRM data already exists
    python manage.py seed_demo --flush    # wipes CRM data first
    python manage.py seed_demo --flush --size small   # a lighter demo (easier to present)
    python manage.py seed_demo --flush --size minimal # 2 of each, for testing by hand

Demo logins (password for all: see DEMO_PASSWORD):
    admin, priya (sales), rahul (sales), sneha (support)

Besides the 150 pipeline deals it adds 240 closed deals spread over the previous 24 months
(so forecasting and RFM segmentation have history) and 80 support tickets. If trained ML
models exist, leads are scored and segments/churn computed at the end.
"""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from faker import Faker

from accounts.models import User
from billing.models import Invoice, Payment, WebhookEvent
from crm.models import Activity, Company, Contact, Deal, Lead, Task
from crm.services import CONTACTING_TYPES, OPEN_LEAD_STATUSES
from support.models import Ticket

from ._demo_text import activity_notes, lead_notes

DEMO_PASSWORD = "LeadPilot@123"
DEMO_USERS = [
    ("admin", "Admin", "User", User.Role.ADMIN),
    ("priya", "Priya", "Sharma", User.Role.SALES),
    ("rahul", "Rahul", "Verma", User.Role.SALES),
    ("sneha", "Sneha", "Iyer", User.Role.SUPPORT),
]
CITIES = ["Mumbai", "Bengaluru", "Delhi", "Pune", "Hyderabad", "Chennai", "Ahmedabad", "Kolkata"]
TAGS = ["vip", "newsletter", "partner", "trial", "enterprise", "smb", "event-2026", "referral"]
ACTIVITY_SUBJECTS = {
    "call": ["Discovery call", "Follow-up call", "Pricing discussion", "Check-in call"],
    "email": ["Sent proposal", "Shared case study", "Follow-up email", "Sent pricing sheet"],
    "meeting": ["Product demo", "On-site meeting", "Quarterly review", "Kick-off meeting"],
    "note": ["Internal note", "Budget update", "Decision-maker identified", "Competitor mentioned"],
}
DEAL_PRODUCTS = [
    "Annual licence",
    "Onboarding package",
    "Pilot",
    "Renewal",
    "Expansion",
    "Consulting",
]
TICKET_TEMPLATES = [
    (
        "Production dashboard is down",
        "Our whole team is locked out since this morning. This is critical, we need it fixed "
        "immediately.",
    ),
    (
        "Charged twice for this month",
        "We were double charged on the latest invoice. Very disappointed, please refund the "
        "extra amount asap.",
    ),
    (
        "Data export broken",
        "The export has stopped working and we lost all our data from yesterday's import. "
        "Terrible experience.",
    ),
    (
        "Thinking about cancelling",
        "Support has been slow and unhelpful. If this isn't resolved we will cancel our "
        "subscription.",
    ),
    (
        "App crashes on login",
        "The mobile app crashes every time I try to log in. Can't access anything. Awful.",
    ),
    (
        "Reports look wrong",
        "The new reports page is confusing and the numbers look wrong to me. Not happy with "
        "the change.",
    ),
    ("Slow page loads", "Pages have been really slow this week, it's frustrating to use."),
    (
        "Disappointing onboarding",
        "The onboarding session was disappointing and didn't cover what we asked for.",
    ),
    ("How do I add a user?", "Can you tell me how to add a new team member to our account?"),
    ("Invoice copy", "Please send a copy of last month's invoice to our finance team."),
    ("Change billing address", "We moved offices. Please update the billing address on file."),
    ("API limits question", "What are the API rate limits on our current plan?"),
    (
        "Great support experience",
        "Thanks for the quick help yesterday, the team was excellent and very friendly.",
    ),
    ("Loving the new pipeline", "The new pipeline view is great, it works perfectly for us."),
    (
        "Feature idea: calendar sync",
        "Really enjoy the product! Would love calendar sync as a future feature.",
    ),
    ("Password reset needed", "Please reset my password asap, I have a client demo in an hour."),
]
# Record counts per demo size. "full" matches the project spec; "small" is easier to present.
SIZES: dict[str, dict[str, int]] = {
    "full": {
        "companies": 50, "contacts": 300, "leads": 400, "activities": 500, "deals": 150,
        "tasks": 120, "history": 240, "customers": 140, "tickets": 80,
    },
    "small": {
        # history still spans 24 months so the forecast and segments have data.
        "companies": 12, "contacts": 40, "leads": 50, "activities": 120, "deals": 24,
        "tasks": 20, "history": 72, "customers": 25, "tickets": 15,
    },
    "minimal": {
        # Two of each, no history: forecast and segments stay empty until deals are won.
        "companies": 2, "contacts": 2, "leads": 2, "activities": 2, "deals": 2,
        "tasks": 2, "history": 0, "customers": 2, "tickets": 2,
    },
}  # fmt: skip

TASK_TITLES = [
    "Send follow-up email", "Schedule demo", "Prepare proposal", "Call back about pricing",
    "Share onboarding docs", "Confirm budget", "Book quarterly review", "Update contact details",
]  # fmt: skip


class Command(BaseCommand):
    help = "Seed demo users, companies, contacts, leads, activities and tasks."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--flush", action="store_true", help="Delete CRM data first.")
        parser.add_argument("--seed", type=int, default=42, help="Random seed.")
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Do nothing if CRM data exists (safe to run on every deploy).",
        )
        parser.add_argument(
            "--size",
            choices=sorted(SIZES),
            default="full",
            help="How much demo data: full (spec volumes), small, or minimal (2 of each).",
        )

    def handle(
        self, *args, flush: bool, seed: int, if_empty: bool, size: str = "full", **options
    ) -> None:
        if if_empty and Contact.objects.exists():
            self.stdout.write("CRM data already exists; skipping seed (--if-empty).")
            return
        if Contact.objects.exists() and not flush:
            raise CommandError("CRM data already exists. Re-run with --flush to replace it.")

        n = SIZES[size]
        random.seed(seed)
        fake = Faker("en_IN")
        Faker.seed(seed)
        now = timezone.now()

        with transaction.atomic():
            if flush:
                from agent.models import AgentRun
                from genai.models import Conversation, DocumentChunk

                for model in (
                    AgentRun,
                    Conversation,
                    DocumentChunk,
                    Payment,
                    WebhookEvent,
                    Invoice,
                    Ticket,
                    Task,
                    Activity,
                    Deal,
                    Lead,
                    Contact,
                    Company,
                ):
                    model.objects.all().delete()

            users = self._users()
            reps = [u for u in users if u.is_sales]

            companies = Company.objects.bulk_create(
                Company(
                    owner=random.choice(reps),
                    name=fake.unique.company(),
                    industry=random.choice(Company.Industry.values),
                    size=random.choice(Company.Size.values),
                    website=f"https://{fake.unique.domain_name()}",
                    city=random.choice(CITIES),
                )
                for _ in range(n["companies"])
            )

            contacts = []
            for i in range(n["contacts"]):
                company = random.choice(companies) if random.random() < 0.85 else None
                first, last = fake.first_name(), fake.last_name()
                contacts.append(
                    Contact(
                        # A contact belongs to the same rep as their company.
                        owner=company.owner if company else random.choice(reps),
                        first_name=first,
                        last_name=last,
                        email=f"{first}.{last}.{i}@example.com".lower().replace(" ", ""),
                        phone=fake.phone_number(),
                        company=company,
                        tags=random.sample(TAGS, k=random.choice([0, 0, 1, 1, 2, 3])),
                    )
                )
            contacts = Contact.objects.bulk_create(contacts)

            leads = Lead.objects.bulk_create(
                Lead(
                    owner=contact.owner,
                    contact=contact,
                    source=random.choices(Lead.Source.values, weights=[30, 20, 25, 10, 15])[0],
                    status=random.choices(Lead.Status.values, weights=[30, 25, 20, 10, 15])[0],
                    budget=Decimal(random.randrange(20_000, 2_000_000, 5_000)),
                    notes=lead_notes(*_who(contact)),
                )
                for contact in random.choices(contacts, k=n["leads"])
            )
            # Spread lead creation over the last 12 months (useful for charts and ML later).
            for lead in leads:
                lead.created_at = now - timedelta(days=random.randint(0, 365))
            Lead.objects.bulk_update(leads, ["created_at"])

            # Engaged leads get more interactions (as in real CRMs), so ML scores line up with
            # lead status instead of being pure noise.
            status_weight = {
                "converted": 5.0,
                "qualified": 4.0,
                "contacted": 2.0,
                "new": 1.0,
                "unqualified": 0.5,
            }
            weight: dict[int, float] = {}
            for lead in leads:
                weight[lead.contact_id] = max(
                    weight.get(lead.contact_id, 0.0), status_weight[lead.status]
                )
            contact_weights = [weight.get(c.id, 1.0) for c in contacts]
            activities = []
            for contact in random.choices(contacts, weights=contact_weights, k=n["activities"]):
                kind = random.choices(Activity.Type.values, weights=[30, 35, 15, 20])[0]
                activities.append(
                    Activity(
                        owner=contact.owner,
                        contact=contact,
                        type=kind,
                        subject=random.choice(ACTIVITY_SUBJECTS[kind]),
                        body=activity_notes(kind, *_who(contact)),
                        occurred_at=now
                        - timedelta(days=random.randint(0, 120), hours=random.randint(0, 23)),
                    )
                )
            Activity.objects.bulk_create(activities)

            # last_contacted_at = latest call/email/meeting with that contact.
            last_contact: dict[int, object] = defaultdict(lambda: None)
            for a in activities:
                if a.type in CONTACTING_TYPES:
                    prev = last_contact[a.contact_id]
                    if prev is None or a.occurred_at > prev:
                        last_contact[a.contact_id] = a.occurred_at
            open_leads = [lead for lead in leads if lead.status in OPEN_LEAD_STATUSES]
            for lead in open_leads:
                lead.last_contacted_at = last_contact[lead.contact_id]
            Lead.objects.bulk_update(open_leads, ["last_contacted_at"])

            deals = self._deals(leads, contacts, now, count=n["deals"])
            with_deal = {d.lead_id for d in deals if d.lead_id}
            orphans = [
                lead
                for lead in leads
                if lead.status == Lead.Status.CONVERTED and lead.pk not in with_deal
            ]
            for lead in orphans:
                lead.status = Lead.Status.QUALIFIED
            Lead.objects.bulk_update(orphans, ["status"])

            tasks = []
            for _ in range(n["tasks"]):
                contact = random.choice(contacts)
                status = random.choices(Task.Status.values, weights=[50, 20, 30])[0]
                tasks.append(
                    Task(
                        owner=contact.owner,
                        assigned_to=contact.owner,
                        contact=contact,
                        title=random.choice(TASK_TITLES),
                        due_date=(now + timedelta(days=random.randint(-10, 21))).date(),
                        status=status,
                        priority=random.choices(Task.Priority.values, weights=[30, 50, 20])[0],
                    )
                )
            Task.objects.bulk_create(tasks)

            history = self._closed_history(
                contacts, now, count=n["history"], customers=n["customers"]
            )
            tickets = self._tickets(contacts, users, now, count=n["tickets"])
            invoices = self._invoices(now)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(users)} users, {len(companies)} companies, {len(contacts)} contacts, "
                f"{len(leads)} leads, {len(deals)} pipeline deals + {len(history)} closed deals "
                f"of history, {len(activities)} activities, {len(tasks)} tasks, "
                f"{len(tickets)} tickets, {len(invoices)} invoices."
            )
        )
        self._apply_ml()
        self._index_rag()
        self.stdout.write(
            "Logins: " + ", ".join(u for u, *_ in DEMO_USERS) + f"  (password: {DEMO_PASSWORD})"
        )

    def _deals(
        self, leads: list[Lead], contacts: list[Contact], now, count: int = 150
    ) -> list[Deal]:
        """Pipeline deals: one per converted lead (up to count), the rest from contacts."""
        converted = [lead for lead in leads if lead.status == Lead.Status.CONVERTED]
        sources: list[tuple[Contact, Lead | None]] = [(lead.contact, lead) for lead in converted]
        extra = min(len(contacts), max(0, count - len(sources)))
        sources += [(c, None) for c in random.sample(contacts, k=extra)]
        stages = random.choices(Deal.Stage.values, weights=[15, 15, 15, 12, 28, 15], k=count)

        deals, positions = [], {stage: 0 for stage in Deal.Stage.values}
        for (contact, lead), stage in zip(sources[:count], stages, strict=False):
            name = contact.company.name if contact.company else contact.full_name
            value = (
                lead.budget
                if lead and lead.budget
                else Decimal(random.randrange(50_000, 1_500_000, 10_000))
            )
            closed = stage in Deal.CLOSED_STAGES
            deal = Deal(
                owner=contact.owner,
                contact=contact,
                lead=lead,
                title=f"{name} – {random.choice(DEAL_PRODUCTS)}",
                value=value,
                stage=stage,
                probability=Deal.DEFAULT_PROBABILITY[stage],
                position=positions[stage],
                closed_at=closed_date(now) if closed else None,
                expected_close_date=(
                    None if closed else (now + timedelta(days=random.randint(7, 90))).date()
                ),
            )
            positions[stage] += 1
            deals.append(deal)
        return Deal.objects.bulk_create(deals)

    def _closed_history(
        self, contacts: list[Contact], now, count: int, customers: int = 140
    ) -> list[Deal]:
        """Won/lost deals from the past 24 months: growing over time, busier in Q4."""
        positions = {
            stage: Deal.objects.filter(stage=stage).count() for stage in Deal.CLOSED_STAGES
        }
        buyers = random.sample(contacts, k=min(len(contacts), customers))  # repeat buyers
        deals = []
        for _ in range(count):
            contact = random.choice(buyers)
            stage = Deal.Stage.WON if random.random() < 0.65 else Deal.Stage.LOST
            name = contact.company.name if contact.company else contact.full_name
            deals.append(
                Deal(
                    owner=contact.owner,
                    contact=contact,
                    title=f"{name} – {random.choice(DEAL_PRODUCTS)}",
                    value=Decimal(random.randrange(50_000, 1_200_000, 10_000)),
                    stage=stage,
                    probability=Deal.DEFAULT_PROBABILITY[stage],
                    position=positions[stage],
                    closed_at=closed_date(now),
                )
            )
            positions[stage] += 1
        return Deal.objects.bulk_create(deals)

    def _tickets(self, contacts: list[Contact], users: list[User], now, count: int) -> list[Ticket]:
        """Support tickets from templates. bulk_create skips the classify signal, so the
        sentiment model is applied explicitly afterwards."""
        from support.services import apply_classification

        support = [u for u in users if u.is_support] or users
        tickets = []
        for _ in range(count):
            subject, body = random.choice(TICKET_TEMPLATES)
            status = random.choices(Ticket.Status.values, weights=[40, 20, 25, 15])[0]
            tickets.append(
                Ticket(
                    owner=random.choice(support),
                    contact=random.choice(contacts),
                    subject=subject,
                    description=body,
                    status=status,
                    assigned_to=random.choice(support) if random.random() < 0.7 else None,
                    resolved_at=now if status in ("resolved", "closed") else None,
                )
            )
        tickets = Ticket.objects.bulk_create(tickets)
        for t in tickets:
            t.created_at = now - timedelta(days=random.randint(0, 60), hours=random.randint(0, 23))
            apply_classification(t)
        Ticket.objects.bulk_update(
            tickets, ["created_at", "sentiment", "sentiment_score", "urgent", "priority"]
        )
        return tickets

    def _index_rag(self) -> None:
        """Build the Ask LeadPilot index. Needs the embedding model (downloaded on first use)."""
        from genai import rag

        try:
            counts = rag.reindex_all()
        except Exception as exc:  # noqa: BLE001 - seeding must not fail because of RAG
            self.stdout.write(f"Search index not built ({exc}). Run `manage.py reindex_all`.")
            return
        self.stdout.write(f"Search index: {counts}")

    def _invoices(self, now) -> list[Invoice]:
        """Invoices for won deals of the last ~4 months: mostly paid, some sent or draft.
        Demo payments use fake test ids (pay_demo_...); no Razorpay call is made."""
        from billing import services as billing

        recent = Deal.objects.filter(
            stage=Deal.Stage.WON, closed_at__gte=now - timedelta(days=120)
        ).order_by("closed_at")
        invoices = []
        for deal in recent:
            invoice = billing.create_invoice(deal, owner=deal.owner, due_in_days=14)
            Invoice.objects.filter(pk=invoice.pk).update(created_at=deal.closed_at)
            roll = random.random()
            if roll < 0.6:
                paid_at = min(deal.closed_at + timedelta(days=random.randint(1, 12)), now)
                Invoice.objects.filter(pk=invoice.pk).update(
                    status=Invoice.Status.PAID, paid_at=paid_at
                )
                Payment.objects.create(
                    invoice=invoice,
                    razorpay_payment_id=f"pay_demo_{invoice.pk:05d}",
                    razorpay_order_id=f"order_demo_{invoice.pk:05d}",
                    amount=invoice.total,
                    method=random.choice(["card", "upi", "netbanking"]),
                    status=Payment.Status.CAPTURED,
                )
            elif roll < 0.85:
                Invoice.objects.filter(pk=invoice.pk).update(status=Invoice.Status.SENT)
            invoices.append(invoice)
        return invoices

    def _apply_ml(self) -> None:
        from ml import services as ml

        status = ml.model_status()
        if not (status["lead_score"] or status["segment"] or status["churn"]):
            self.stdout.write("ML models not trained yet: run `python manage.py ml_train`.")
            return
        scored = ml.rescore_all()
        insights = ml.refresh_customer_insights()
        self.stdout.write(
            f"ML: scored {scored} leads; {insights['segmented']} customers segmented, "
            f"{insights['churn_scored']} churn-scored."
        )

    def _users(self) -> list[User]:
        users = []
        for username, first, last, role in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": role,
                    "email": f"{username}@leadpilot.demo",
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                if role == User.Role.ADMIN:
                    user.is_staff = user.is_superuser = True
                user.save()
            users.append(user)
        return users


def closed_date(now):
    """A close date within the last 24 months; recent months and Oct-Dec are busier."""

    def month_weight(months_ago: int) -> float:
        month = (now.month - months_ago - 1) % 12 + 1
        return (24 - months_ago) * (1.4 if month in (10, 11, 12) else 1.0)

    months_ago = random.choices(range(24), weights=[month_weight(m) for m in range(24)])[0]
    start = now.replace(day=1, hour=10, minute=0, second=0, microsecond=0)
    for _ in range(months_ago):
        start = (start - timedelta(days=1)).replace(day=1)
    latest = now if months_ago == 0 else start + timedelta(days=27)
    span = max((latest - start).days, 1)
    return start + timedelta(days=random.randint(0, span - 1), hours=random.randint(0, 8))


def _who(contact: Contact) -> tuple[str, str, str]:
    company = contact.company
    return (
        contact.first_name,
        company.city if company and company.city else "Mumbai",
        company.get_industry_display().lower() if company else "retail",
    )
