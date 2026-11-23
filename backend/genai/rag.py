"""Ask LeadPilot: retrieval-augmented answers over CRM notes, activities and tickets.

Index:    Activity / Ticket / Lead notes -> ~500-char chunks (50 overlap) -> 384-d embeddings
          -> genai.DocumentChunk (pgvector on Postgres). Kept fresh by signals + Celery.
Retrieve: scope to what the user may see -> optional company/contact + date filters parsed
          from the question -> top-5 cosine similarity.
Answer:   grounded prompt with numbered sources -> JSON {answer, sources} -> citations
          [{type, id, snippet, ...}]. Weak or missing context -> "I don't know".
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

import numpy as np
from django.db import connection, transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from pydantic import BaseModel, Field

from accounts.models import User
from crm.models import Activity, Company, Contact, Lead
from support.models import Ticket

from . import embeddings
from .models import Conversation, ConversationMessage, DocumentChunk
from .prompts import fence, render

TOP_K = 5
HISTORY_TURNS = 6
SNIPPET_CHARS = 180
DONT_KNOW = "I don't know based on the CRM records I can see."
Source = DocumentChunk.Source


def min_similarity() -> float:
    return float(os.environ.get("RAG_MIN_SIMILARITY", "0.35"))


# --- Building documents ---------------------------------------------------------------------


@dataclass
class Document:
    source_type: str
    source_id: int
    text: str
    owner_id: int | None
    contact_id: int | None
    company_id: int | None
    occurred_at: datetime | None


def _who(contact: Contact) -> str:
    company = f" ({contact.company.name})" if contact.company_id else ""
    return f"{contact.full_name}{company}"


def document_for(source_type: str, obj) -> Document | None:
    """The text we index for one CRM record (None = nothing worth indexing)."""
    if source_type == Source.ACTIVITY:
        c = obj.contact
        text = (
            f"{obj.get_type_display()} with {_who(c)} on {obj.occurred_at:%d %b %Y}: "
            f"{obj.subject}. {obj.body or ''} {obj.summary or ''}"
        )
        return Document(source_type, obj.id, text, obj.owner_id, c.id, c.company_id,
                        obj.occurred_at)  # fmt: skip
    if source_type == Source.TICKET:
        c = obj.contact
        comments = " ".join(cm.body for cm in obj.comments.all())
        text = (
            f"Support ticket from {_who(c)} opened {obj.created_at:%d %b %Y} "
            f"({obj.get_status_display()}, {obj.get_priority_display()} priority): "
            f"{obj.subject}. {obj.description} {comments}"
        )
        return Document(source_type, obj.id, text, c.owner_id, c.id, c.company_id, obj.created_at)
    if source_type == Source.LEAD:
        if not (obj.notes or "").strip():
            return None
        c = obj.contact
        text = (
            f"Lead notes for {_who(c)} (status {obj.get_status_display()}, source "
            f"{obj.get_source_display()}, created {obj.created_at:%d %b %Y}): {obj.notes}"
        )
        return Document(source_type, obj.id, text, obj.owner_id, c.id, c.company_id,
                        obj.created_at)  # fmt: skip
    raise ValueError(f"Unknown source type {source_type}")


MODELS = {Source.ACTIVITY: Activity, Source.TICKET: Ticket, Source.LEAD: Lead}
RELATED = {
    Source.ACTIVITY: ("contact__company",),
    Source.TICKET: ("contact__company",),
    Source.LEAD: ("contact__company",),
}


# --- Indexing -------------------------------------------------------------------------------


def _hash(text: str) -> str:
    return hashlib.sha256(f"{embeddings.backend()}|{text}".encode()).hexdigest()


def index_documents(docs: list[Document]) -> int:
    """(Re)index documents: skip unchanged ones, replace chunks of changed ones."""
    if not docs:
        return 0
    existing = {
        (r["source_type"], r["source_id"]): r["content_hash"]
        for r in DocumentChunk.objects.filter(
            source_type__in={d.source_type for d in docs},
            source_id__in={d.source_id for d in docs},
            chunk_index=0,
        ).values("source_type", "source_id", "content_hash")
    }
    todo = [d for d in docs if existing.get((d.source_type, d.source_id)) != _hash(d.text)]
    if not todo:
        return 0
    pieces = [(d, i, chunk) for d in todo for i, chunk in enumerate(embeddings.chunk_text(d.text))]
    vectors = embeddings.embed_texts([p[2] for p in pieces])
    with transaction.atomic():
        for d in todo:
            DocumentChunk.objects.filter(source_type=d.source_type, source_id=d.source_id).delete()
        DocumentChunk.objects.bulk_create(
            [
                DocumentChunk(
                    source_type=d.source_type,
                    source_id=d.source_id,
                    chunk_index=i,
                    text=chunk,
                    embedding=vectors[n].tolist(),
                    owner_id=d.owner_id,
                    contact_id=d.contact_id,
                    company_id=d.company_id,
                    occurred_at=d.occurred_at,
                    content_hash=_hash(d.text),
                )
                for n, (d, i, chunk) in enumerate(pieces)
            ],
            batch_size=500,
        )
    return len(todo)


def index_source(source_type: str, source_id: int) -> int:
    obj = (
        MODELS[source_type]
        .objects.select_related(*RELATED[source_type])
        .filter(pk=source_id)
        .first()
    )
    if obj is None:
        delete_source(source_type, source_id)
        return 0
    doc = document_for(source_type, obj)
    if doc is None:
        delete_source(source_type, source_id)
        return 0
    return index_documents([doc])


def delete_source(source_type: str, source_id: int) -> None:
    DocumentChunk.objects.filter(source_type=source_type, source_id=source_id).delete()


def reindex_all(batch: int = 200) -> dict[str, int]:
    """Index every activity, ticket and lead note (unchanged ones are skipped)."""
    counts = {}
    for source_type, model in MODELS.items():
        qs = model.objects.select_related(*RELATED[source_type]).order_by("pk")
        if source_type == Source.TICKET:
            qs = qs.prefetch_related("comments")
        done, buffer = 0, []
        for obj in qs.iterator(chunk_size=batch):
            doc = document_for(source_type, obj)
            if doc:
                buffer.append(doc)
            if len(buffer) >= batch:
                done += index_documents(buffer)
                buffer = []
        done += index_documents(buffer)
        live = set(model.objects.values_list("pk", flat=True))
        DocumentChunk.objects.filter(source_type=source_type).exclude(source_id__in=live).delete()
        counts[str(source_type.value)] = done
    return counts


# --- Retrieval ------------------------------------------------------------------------------


def scope(user: User) -> QuerySet[DocumentChunk]:
    """Chunks this user may read: admin all, sales their own, support all tickets."""
    chunks = DocumentChunk.objects.all()
    if user.is_admin:
        return chunks
    if user.is_support:
        return chunks.filter(source_type=Source.TICKET)
    return chunks.filter(owner=user)


def mentioned_entities(question: str, user: User) -> tuple[set[int], set[int]]:
    """Company and contact ids whose names appear in the question (within the user's scope)."""
    q = question
    companies = (
        Company.objects.all()
        if user.is_admin or user.is_support
        else Company.objects.filter(owner=user)
    )
    company_ids = {
        c.id for c in companies.only("id", "name") if len(c.name) > 2 and _mentions(q, c.name)
    }
    contacts = (
        Contact.objects.all()
        if user.is_admin or user.is_support
        else Contact.objects.filter(owner=user)
    )
    contact_ids = {
        c.id
        for c in contacts.only("id", "first_name", "last_name")
        if c.last_name and _mentions(q, f"{c.first_name} {c.last_name}")
    }
    return company_ids, contact_ids


def _normalize(text: str) -> str:
    """Lowercase, punctuation -> spaces, collapse spaces ("Bhagat-Chaudhari" -> "bhagat chaudhari")."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


_SUFFIXES = re.compile(r"\b(pvt|private|ltd|limited|inc|llp|plc|and|sons|co|group)\b")


def _core(text: str) -> str:
    """Normalized text without legal suffixes / filler words ("Sami, Bhatt and Rajan Ltd" ->
    "sami bhatt rajan"), applied to both the name and the question so they compare equal."""
    return re.sub(r"\s+", " ", _SUFFIXES.sub(" ", _normalize(text))).strip()


def _mentions(haystack: str, name: str) -> bool:
    """Does the question mention this company/contact name?"""
    core = _core(name)
    return bool(core) and re.search(rf"\b{re.escape(core)}\b", _core(haystack)) is not None


def date_range(question: str, now: datetime | None = None) -> tuple[datetime, datetime] | None:
    """Turn 'last month', 'this week', 'yesterday', 'last 30 days'... into [start, end)."""
    now = now or timezone.localtime()
    q = question.lower()
    today = timezone.make_aware(datetime.combine(now.date(), time.min))
    month_start = today.replace(day=1)
    if "last month" in q or "previous month" in q:
        prev_start = (month_start - timedelta(days=1)).replace(day=1)
        return prev_start, month_start
    if "this month" in q:
        return month_start, now + timedelta(seconds=1)
    week_start = today - timedelta(days=today.weekday())
    if "last week" in q or "previous week" in q:
        return week_start - timedelta(days=7), week_start
    if "this week" in q:
        return week_start, now + timedelta(seconds=1)
    if "yesterday" in q:
        return today - timedelta(days=1), today
    if "today" in q:
        return today, now + timedelta(seconds=1)
    if m := re.search(r"last (\d{1,3}) days", q):
        return today - timedelta(days=int(m.group(1))), now + timedelta(seconds=1)
    return None


@dataclass
class Hit:
    chunk: DocumentChunk
    similarity: float
    # True when the question named this record's company/contact: it is relevant by
    # construction, whatever its embedding similarity (weak with hash embeddings).
    pinned: bool = False


def search(question: str, user: User, k: int = TOP_K) -> tuple[list[Hit], bool]:
    """Top-k chunks for the question. Returns (hits, filtered) where `filtered` says whether a
    company/contact or date filter from the question narrowed the search."""
    candidates = scope(user)
    company_ids, contact_ids = mentioned_entities(question, user)
    if company_ids or contact_ids:
        candidates = candidates.filter(
            Q(company_id__in=company_ids) | Q(contact_id__in=contact_ids)
        )
    if span := date_range(question):
        candidates = candidates.filter(occurred_at__gte=span[0], occurred_at__lt=span[1])
    filtered = bool(company_ids or contact_ids or span)
    pinned = bool(company_ids or contact_ids)
    query = embeddings.embed_query(question)

    if connection.vendor == "postgresql":
        from pgvector.django import CosineDistance

        rows = candidates.annotate(distance=CosineDistance("embedding", query.tolist())).order_by(
            "distance"
        )[:k]
        hits = [Hit(c, 1.0 - float(c.distance), pinned) for c in rows]
    else:  # SQLite (local dev): brute-force cosine in NumPy
        rows = list(candidates)
        if not rows:
            return [], filtered
        matrix = np.vstack([np.asarray(c.embedding, dtype=np.float32) for c in rows])
        scores = matrix @ query
        order = np.argsort(-scores)[:k]
        hits = [Hit(rows[i], float(scores[i]), pinned) for i in order]
    return hits, filtered


# --- Answering ------------------------------------------------------------------------------


class RagAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)
    sources: list[int] = Field(default_factory=list, max_length=TOP_K)


def _link(chunk: DocumentChunk) -> str:
    if chunk.source_type == Source.TICKET:
        return f"/tickets?ticket={chunk.source_id}"
    return f"/contacts/{chunk.contact_id}" if chunk.contact_id else ""


def citation(chunk: DocumentChunk, similarity: float) -> dict[str, Any]:
    snippet = chunk.text if len(chunk.text) <= SNIPPET_CHARS else chunk.text[:SNIPPET_CHARS] + "…"
    return {
        "type": chunk.source_type,
        "id": chunk.source_id,
        "snippet": snippet,
        "contact_id": chunk.contact_id,
        "date": chunk.occurred_at.date().isoformat() if chunk.occurred_at else None,
        "link": _link(chunk),
        "similarity": round(similarity, 3),
    }


def answer(question: str, user: User, conversation: Conversation | None = None) -> dict[str, Any]:
    """Answer from the user's CRM data with citations, and store the exchange."""

    if conversation is None:
        conversation = Conversation.objects.create(user=user, title=question.strip()[:200])
    history = list(conversation.messages.order_by("-created_at", "-id")[:HISTORY_TURNS])[::-1]
    ConversationMessage.objects.create(conversation=conversation, role="user", content=question)

    text, citations = grounded_answer(
        question, user, [{"role": m.role, "content": m.content} for m in history]
    )

    ConversationMessage.objects.create(
        conversation=conversation, role="assistant", content=text, citations=citations
    )
    conversation.save(update_fields=["updated_at"])
    return {"conversation_id": conversation.id, "answer": text, "citations": citations}


def grounded_answer(
    question: str, user: User, history: list[dict[str, str]] | None = None
) -> tuple[str, list[dict[str, Any]]]:
    """Retrieve + answer without storing anything (used by the chat and by the agent)."""
    from .services import structured_chat

    hits, filtered = search(question, user)
    # A named company/contact pins the right records: keep them. A date filter alone only
    # narrows the search, so it relaxes the similarity threshold instead of removing it.
    threshold = min_similarity() * (0.5 if filtered else 1.0)
    hits = [h for h in hits if h.pinned or h.similarity >= threshold]

    if not hits:
        text, citations = DONT_KNOW, []
    else:
        sources = "\n\n".join(
            (
                f"[{n}] ({h.chunk.get_source_type_display()} #{h.chunk.source_id}, "
                f"{h.chunk.occurred_at:%d %b %Y}) {h.chunk.text}"
                if h.chunk.occurred_at
                else f"[{n}] ({h.chunk.get_source_type_display()} #{h.chunk.source_id}) {h.chunk.text}"
            )
            for n, h in enumerate(hits, start=1)
        )
        system = render(
            "rag_answer",
            today=timezone.localdate().strftime("%d %b %Y"),
            user_name=user.get_full_name() or user.username,
            role=user.get_role_display(),
            sources=fence(sources),
        )
        messages = [{"role": "system", "content": system}, *(history or [])]
        messages.append({"role": "user", "content": question})
        result = structured_chat(messages, RagAnswer, purpose="rag_answer", user=user)
        used = sorted({n for n in result.sources if 1 <= n <= len(hits)})
        text = result.answer.strip()
        if text.lower().startswith("i don't know"):
            citations = []
        else:
            citations = [citation(hits[n - 1].chunk, hits[n - 1].similarity) for n in used]
    return text, citations
