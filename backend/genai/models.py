"""GenAI records: LLM usage log (Phase 4)."""

from django.conf import settings
from django.db import models
from pgvector.django import VectorField


class LLMCall(models.Model):
    """One request to an LLM provider: who, why, which model, tokens, latency, outcome."""

    class Status(models.TextChoices):
        OK = "ok", "OK"
        ERROR = "error", "Error"
        INVALID_OUTPUT = "invalid_output", "Invalid output"
        REFUSED = "refused", "Refused"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    purpose = models.CharField(max_length=40)
    provider = models.CharField(max_length=20)
    model = models.CharField(max_length=80)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    attempts = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OK)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["purpose", "created_at"])]

    def __str__(self) -> str:
        return f"{self.provider}:{self.model} {self.purpose} ({self.status})"

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


# --- RAG (Phase 5) ---------------------------------------------------------------------------

EMBEDDING_DIM = 384


class DocumentChunk(models.Model):
    """A searchable piece of CRM text with its embedding.

    On Postgres the embedding is a pgvector `vector(384)` column with an HNSW cosine index
    (created in the migration, Postgres only). On SQLite the same field is stored as text and
    search falls back to NumPy in Python, which is fine for local development.
    """

    class Source(models.TextChoices):
        ACTIVITY = "activity", "Activity"
        TICKET = "ticket", "Ticket"
        LEAD = "lead", "Lead notes"

    source_type = models.CharField(max_length=10, choices=Source.choices)
    source_id = models.PositiveIntegerField()
    chunk_index = models.PositiveSmallIntegerField(default=0)
    text = models.TextField()
    embedding = VectorField(dimensions=EMBEDDING_DIM)
    # Denormalized for filtering before vector search.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    contact = models.ForeignKey(
        "crm.Contact", on_delete=models.CASCADE, null=True, related_name="+"
    )
    company = models.ForeignKey(
        "crm.Company", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    occurred_at = models.DateTimeField(null=True)
    content_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["source_type", "source_id", "chunk_index"]
        indexes = [
            models.Index(fields=["source_type", "source_id"]),
            models.Index(fields=["owner", "occurred_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.source_type}:{self.source_id}#{self.chunk_index}"


class Conversation(models.Model):
    """An Ask LeadPilot chat thread."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations"
    )
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title


class ConversationMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    citations = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:40]}"
