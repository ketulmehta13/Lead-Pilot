"""Text chunking and embeddings for RAG.

Backends (env EMBEDDINGS_BACKEND):
    sentence-transformers  all-MiniLM-L6-v2, 384 dims (default). Downloaded once (~90 MB)
                           from Hugging Face on first use, then cached.
    hash                   deterministic feature hashing into 384 dims. No download, used in
                           tests/CI; it captures word overlap only, not meaning.
Vectors are L2-normalized, so cosine similarity == dot product.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from functools import cache

import numpy as np

logger = logging.getLogger(__name__)

DIM = 384
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
MODEL_NAME = os.environ.get("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def backend() -> str:
    return os.environ.get("EMBEDDINGS_BACKEND", "sentence-transformers").strip().lower()


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split into ~`size`-char chunks overlapping by `overlap` chars, preferring to cut at a
    sentence end, then a space, so words are not split."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start:end]
            cut = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
            if cut < size // 2:
                cut = window.rfind(" ")
            if cut > size // 4:
                end = start + cut + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
        # Don't start the next chunk mid-word.
        while start < len(text) and start > 0 and text[start - 1] != " ":
            start += 1
    return chunks


@cache
def _model():
    from sentence_transformers import SentenceTransformer

    logger.info("Loading embedding model %s", MODEL_NAME)
    return SentenceTransformer(MODEL_NAME, device="cpu")


_TOKEN = re.compile(r"[a-z0-9]+")


def _hash_embed(text: str) -> np.ndarray:
    vec = np.zeros(DIM, dtype=np.float32)
    words = _TOKEN.findall(text.lower())
    for token in words + [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]:
        digest = hashlib.md5(token.encode(), usedforsecurity=False).digest()
        index = int.from_bytes(digest[:4], "little") % DIM
        vec[index] += 1.0 if digest[4] % 2 else -1.0
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embeddings for `texts`, shape (len(texts), 384), L2-normalized."""
    if not texts:
        return np.zeros((0, DIM), dtype=np.float32)
    if backend() == "hash":
        return np.vstack([_hash_embed(t) for t in texts])
    vectors = _model().encode(
        texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False
    )
    return np.asarray(vectors, dtype=np.float32)


def embed_query(text: str) -> np.ndarray:
    return embed_texts([text])[0]
