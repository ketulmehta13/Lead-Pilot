"""Fill the database with realistic demo data.

    python manage.py seed_demo            # refuses if CRM data already exists
    python manage.py seed_demo --flush    # wipes CRM data first

Demo logins (password for all: see DEMO_PASSWORD):
    admin, priya (sales), rahul (sales), sneha (support)

Tickets (Phase 3) are seeded once that model exists.
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
from crm.models import Activity, Company, Contact, Deal, Lead, Task
from crm.services import CONTACTING_TYPES, OPEN_LEAD_STATUSES

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
TASK_TITLES = [
    "Send follow-up email", "Schedule demo", "Prepare proposal", "Call back about pricing",
    "Share onboarding docs", "Confirm budget", "Book quarterly review", "Update contact details",
]  # fmt: skip


class Command(BaseCommand):
    help = "Seed demo users, companies, contacts, leads, activities and tasks."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--flush", action="store_true", help="Delete CRM data first.")
        parser.add_argument("--seed", type=int, default=42, help="Random seed.")

    def handle(self, *args, flush: bool, seed: int, **options) -> None:
        if Contact.objects.exists() and not flush:
            raise CommandError("CRM data already exists. Re-run with --flush to replace it.")

        random.seed(seed)
        fake = Faker("en_IN")
        Faker.seed(seed)
        now = timezone.now()

        with transaction.atomic():
            if flush:
                for model in (Task, Activity, Deal, Lead, Contact, Company):
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
                for _ in range(50)
            )

            contacts = []
            for i in range(300):
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
                    notes=fake.paragraph(nb_sentences=2),
                )
                for contact in random.choices(contacts, k=400)
            )
            # Spread lead creation over the last 12 months (useful for charts and ML later).
            for lead in leads:
                lead.created_at = now - timedelta(days=random.randint(0, 365))
            Lead.objects.bulk_update(leads, ["created_at"])

            activities = []
            for _ in range(500):
                contact = random.choice(contacts)
                kind = random.choices(Activity.Type.values, weights=[30, 35, 15, 20])[0]
                activities.append(
                    Activity(
                        owner=contact.owner,
                        contact=contact,
                        type=kind,
                        subject=random.choice(ACTIVITY_SUBJECTS[kind]),
                        body=fake.paragraph(nb_sentences=random.randint(2, 6)),
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

            deals = self._deals(leads, contacts, now)

            tasks = []
            for _ in range(120):
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

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(users)} users, {len(companies)} companies, {len(contacts)} contacts, "
                f"{len(leads)} leads, {len(deals)} deals, {len(activities)} activities, "
                f"{len(tasks)} tasks."
            )
        )
        self.stdout.write(
            "Logins: " + ", ".join(u for u, *_ in DEMO_USERS) + f"  (password: {DEMO_PASSWORD})"
        )

    def _deals(self, leads: list[Lead], contacts: list[Contact], now) -> list[Deal]:
        """150 deals: one per converted lead, the rest straight from contacts."""
        converted = [lead for lead in leads if lead.status == Lead.Status.CONVERTED]
        sources: list[tuple[Contact, Lead | None]] = [(lead.contact, lead) for lead in converted]
        sources += [(c, None) for c in random.sample(contacts, k=max(0, 150 - len(sources)))]
        stages = random.choices(Deal.Stage.values, weights=[15, 15, 15, 12, 28, 15], k=150)

        deals, positions = [], {stage: 0 for stage in Deal.Stage.values}
        for (contact, lead), stage in zip(sources[:150], stages, strict=False):
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
                # Wins/losses spread over the last 12 months feed the revenue trend.
                closed_at=now - timedelta(days=random.randint(0, 360)) if closed else None,
                expected_close_date=(
                    None if closed else (now + timedelta(days=random.randint(7, 90))).date()
                ),
            )
            positions[stage] += 1
            deals.append(deal)
        return Deal.objects.bulk_create(deals)

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
