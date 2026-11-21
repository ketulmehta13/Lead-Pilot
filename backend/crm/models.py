"""Core CRM records. Deal (and the deal links on Activity/Task) arrive in Phase 2."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from common.models import OwnedModel


class Company(OwnedModel):
    class Industry(models.TextChoices):
        TECHNOLOGY = "technology", "Technology"
        FINANCE = "finance", "Finance"
        HEALTHCARE = "healthcare", "Healthcare"
        RETAIL = "retail", "Retail"
        MANUFACTURING = "manufacturing", "Manufacturing"
        EDUCATION = "education", "Education"
        REAL_ESTATE = "real_estate", "Real estate"
        HOSPITALITY = "hospitality", "Hospitality"
        OTHER = "other", "Other"

    class Size(models.TextChoices):
        S1_10 = "1-10", "1–10"
        S11_50 = "11-50", "11–50"
        S51_200 = "51-200", "51–200"
        S201_1000 = "201-1000", "201–1000"
        S1000_PLUS = "1000+", "1000+"

    name = models.CharField(max_length=200)
    industry = models.CharField(max_length=20, choices=Industry.choices, default=Industry.OTHER)
    size = models.CharField(max_length=10, choices=Size.choices, blank=True)
    website = models.URLField(blank=True)
    city = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "companies"

    def __str__(self) -> str:
        return self.name


class Contact(OwnedModel):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    company = models.ForeignKey(
        Company, on_delete=models.SET_NULL, null=True, blank=True, related_name="contacts"
    )
    tags = models.JSONField(default=list, blank=True)
    # Filled by ML in Phase 3.
    segment = models.CharField(max_length=30, null=True, blank=True)  # noqa: DJ001
    churn_risk = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        return self.full_name


class Lead(OwnedModel):
    class Source(models.TextChoices):
        WEB = "web", "Web"
        REFERRAL = "referral", "Referral"
        ADS = "ads", "Ads"
        EVENT = "event", "Event"
        COLD = "cold", "Cold outreach"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        UNQUALIFIED = "unqualified", "Unqualified"
        CONVERTED = "converted", "Converted"

    class ScoreLabel(models.TextChoices):
        HOT = "hot", "Hot"
        WARM = "warm", "Warm"
        COLD = "cold", "Cold"

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="leads")
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.WEB)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    # Filled by ML in Phase 3.
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    score_label = models.CharField(  # noqa: DJ001 - null = not scored yet
        max_length=4, choices=ScoreLabel.choices, null=True, blank=True
    )
    score_explanation = models.JSONField(null=True, blank=True)
    last_contacted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["source"])]

    def __str__(self) -> str:
        return f"Lead: {self.contact} ({self.get_status_display()})"


class Activity(OwnedModel):
    class Type(models.TextChoices):
        CALL = "call", "Call"
        EMAIL = "email", "Email"
        MEETING = "meeting", "Meeting"
        NOTE = "note", "Note"

    type = models.CharField(max_length=10, choices=Type.choices, default=Type.NOTE)
    subject = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="activities")
    # Filled by GenAI in Phase 4.
    summary = models.TextField(null=True, blank=True)  # noqa: DJ001 - null = not summarised yet
    action_items = models.JSONField(null=True, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name_plural = "activities"

    def __str__(self) -> str:
        return f"{self.get_type_display()}: {self.subject}"


class Task(OwnedModel):
    class Status(models.TextChoices):
        TODO = "todo", "To do"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.TODO)
    priority = models.CharField(max_length=6, choices=Priority.choices, default=Priority.MEDIUM)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks"
    )
    created_by_agent = models.BooleanField(default=False)

    class Meta:
        ordering = ["status", "due_date", "-created_at"]

    def __str__(self) -> str:
        return self.title
