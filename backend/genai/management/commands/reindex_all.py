"""Rebuild the Ask LeadPilot search index (embeddings for activities, tickets, lead notes)."""

import time

from django.core.management.base import BaseCommand

from genai import embeddings, rag


class Command(BaseCommand):
    help = "Embed every activity, ticket and lead note into DocumentChunk (unchanged are skipped)."

    def handle(self, *args, **options) -> None:
        self.stdout.write(f"Embedding backend: {embeddings.backend()} ({embeddings.MODEL_NAME})")
        start = time.time()
        counts = rag.reindex_all()
        total = rag.DocumentChunk.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Indexed {counts} in {time.time() - start:.0f}s; {total} chunks in the index."
            )
        )
