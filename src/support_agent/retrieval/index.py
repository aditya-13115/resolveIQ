"""Retrieval index building for ResolveIQ.

Provides canonical normalization, the Corpus dataclass, and builders
for the retrieval indices used in 05_retrieval.ipynb and 06_agent.ipynb.

Public API:
    normalize_text(text) -> str
    text_hash(text) -> str
    Corpus                              # dataclass
    build_tfidf_index(corpus, **kw)     # returns fitted vectorizer + matrix
    build_bm25_index(corpus, **kw)
    build_embedding_index(corpus, model_name)
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

# ---- Version pin. Bump only if normalization logic changes. ----
NORMALIZATION_VERSION = "retrieval_text_v1"


# ---------- Normalization ----------
_URL_RE     = re.compile(r"https?://\S+|www\.\S+")
_MENTION_RE = re.compile(r"(?<!\w)@\w+")
_WS_RE      = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Canonical normalization. Every path that hashes or compares text
    (corpus build, dev/test exclusion, dedup, leakage checks) MUST use this."""
    t = str(text).lower()
    t = _URL_RE.sub(" ", t)
    t = _MENTION_RE.sub(" ", t)
    t = _WS_RE.sub(" ", t)
    return t.strip()


def text_hash(text: str) -> str:
    """SHA-256 of normalized text. Used for cross-split leakage detection."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


# ---------- Corpus ----------
@dataclass
class Corpus:
    """The retrieval benchmark corpus.

    One row per historical thread. Fields align by index.
    """
    doc_ids:         np.ndarray              # (N,) int, root_ids
    customer_texts:  list[str]               # (N,) raw customer messages
    normalized:      list[str]               # (N,) normalized
    intents:         np.ndarray              # (N,) str
    response_texts:  list[str]               # (N,) grounding response
    response_types:  np.ndarray              # (N,) str
    source:          np.ndarray              # (N,) str
    normalization_version: str = NORMALIZATION_VERSION

    def __len__(self) -> int:
        return len(self.doc_ids)

    def doc_id_to_index(self) -> dict[int, int]:
        return {int(d): i for i, d in enumerate(self.doc_ids)}

    # ---- Persistence ----
    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame({
            "doc_id":         self.doc_ids.astype(int),
            "customer_text":  self.customer_texts,
            "normalized":     self.normalized,
            "intent":         self.intents.astype(str),
            "response_text":  self.response_texts,
            "response_type":  self.response_types.astype(str),
            "source":         self.source.astype(str),
        })

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> "Corpus":
        return cls(
            doc_ids         = df["doc_id"].to_numpy(dtype=int),
            customer_texts  = df["customer_text"].astype(str).tolist(),
            normalized      = df["normalized"].astype(str).tolist(),
            intents         = df["intent"].astype(str).to_numpy(),
            response_texts  = df["response_text"].astype(str).tolist(),
            response_types  = df["response_type"].astype(str).to_numpy(),
            source          = df["source"].astype(str).to_numpy(),
        )

    def save_jsonl(self, path: Path) -> str:
        """Write corpus as JSONL, one doc per line. Returns SHA-256 of the file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for i in range(len(self)):
                f.write(json.dumps({
                    "doc_id":         int(self.doc_ids[i]),
                    "customer_text":  self.customer_texts[i],
                    "normalized":     self.normalized[i],
                    "intent":         str(self.intents[i]),
                    "response_text":  self.response_texts[i],
                    "response_type":  str(self.response_types[i]),
                    "source":         str(self.source[i]),
                    "normalization_version": self.normalization_version,
                }, ensure_ascii=False) + "\n")
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @classmethod
    def load_jsonl(cls, path: Path) -> "Corpus":
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                rows.append(json.loads(line))
        df = pd.DataFrame(rows)
        return cls.from_dataframe(df)


# ---------- Indices ----------
def build_tfidf_index(corpus: Corpus, *, ngram_range=(1, 2), min_df: int = 1):
    """Fit a TF-IDF index over corpus.normalized. Returns (vectorizer, matrix)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    vec = TfidfVectorizer(
        ngram_range=ngram_range,
        min_df=min_df,
        sublinear_tf=True,
        strip_accents="unicode",
    )
    matrix = vec.fit_transform(corpus.normalized)
    return vec, matrix


def build_bm25_index(corpus: Corpus, *, k1: float = 1.5, b: float = 0.75):
    """Fit BM25 over whitespace-tokenized normalized text.
    Returns (bm25, tokenization_name)."""
    try:
        from rank_bm25 import BM25Okapi
    except ImportError as e:
        raise ImportError(
            "rank_bm25 is required for BM25Retriever. "
            "Install with: uv add rank-bm25"
        ) from e
    tokenized = [t.split() for t in corpus.normalized]
    bm25 = BM25Okapi(tokenized, k1=k1, b=b)
    return bm25, "normalized_whitespace_v1"


def build_embedding_index(corpus: Corpus, model_name: str = "all-MiniLM-L6-v2"):
    """Encode corpus messages. Returns (embeddings, model_name).
    Embeddings are L2-normalized so cosine == dot product."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise ImportError(
            "sentence-transformers is required for EmbeddingRetriever. "
            "Install with: uv add sentence-transformers"
        ) from e
    model = SentenceTransformer(model_name)
    embeddings = model.encode(
        corpus.customer_texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return (model, embeddings), model_name