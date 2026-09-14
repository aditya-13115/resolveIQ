"""Retriever implementations for 05_retrieval.ipynb.

Every retriever exposes:
    .name -> str
    .retrieve(query: str, k: int = 10, filter_mask: np.ndarray | None = None)
        -> list[tuple[int, float]]  # (doc_id, score), highest first

filter_mask is an optional boolean array of len(corpus). When provided, only
docs where filter_mask[i] is True are eligible.
"""
from __future__ import annotations

from typing import Protocol

import numpy as np

from .index import (
    Corpus, normalize_text,
    build_tfidf_index, build_bm25_index, build_embedding_index,
)


# ---------- Base ----------
class BaseRetriever:
    name: str = "base"

    def __init__(self, corpus: Corpus):
        self.corpus = corpus

    def retrieve(self, query: str, k: int = 10,
                 filter_mask: np.ndarray | None = None) -> list[tuple[int, float]]:
        raise NotImplementedError


def _apply_mask(scores: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    if mask is None:
        return scores
    if mask.dtype != bool or mask.shape[0] != scores.shape[0]:
        raise ValueError("filter_mask must be boolean array of len(corpus)")
    return np.where(mask, scores, -np.inf)


def _topk_from_scores(scores: np.ndarray, doc_ids: np.ndarray, k: int,
                       min_score: float = 0.0):
    order = np.argsort(scores)[::-1]
    out = []
    for i in order[:k]:
        s = float(scores[i])
        if not np.isfinite(s) or s <= min_score:
            break
        out.append((int(doc_ids[i]), s))
    return out


# ---------- Random ----------
class RandomRetriever(BaseRetriever):
    name = "random"

    def __init__(self, corpus: Corpus, seed: int = 42):
        super().__init__(corpus)
        self.rng = np.random.RandomState(seed)
        self.seed = seed

    def retrieve(self, query: str, k: int = 10,
                 filter_mask: np.ndarray | None = None) -> list[tuple[int, float]]:
        n = len(self.corpus)
        pool = np.arange(n) if filter_mask is None else np.where(filter_mask)[0]
        if len(pool) == 0:
            return []
        take = min(k, len(pool))
        idx = self.rng.choice(pool, size=take, replace=False)
        # Assign descending arbitrary scores so ranks are defined
        return [(int(self.corpus.doc_ids[i]), float(take - j))
                for j, i in enumerate(idx)]


# ---------- TF-IDF ----------
class TFIDFRetriever(BaseRetriever):
    name = "tfidf"

    def __init__(self, corpus: Corpus, *, ngram_range=(1, 2), min_df: int = 1):
        super().__init__(corpus)
        self.vec, self.matrix = build_tfidf_index(
            corpus, ngram_range=ngram_range, min_df=min_df
        )
        self.params = {"ngram_range": ngram_range, "min_df": min_df}

    def retrieve(self, query: str, k: int = 10,
                 filter_mask: np.ndarray | None = None) -> list[tuple[int, float]]:
        from sklearn.metrics.pairwise import cosine_similarity
        q = self.vec.transform([normalize_text(query)])
        sims = cosine_similarity(q, self.matrix).ravel()
        sims = _apply_mask(sims, filter_mask)
        return _topk_from_scores(sims, self.corpus.doc_ids, k, min_score=0.0)


# ---------- BM25 ----------
class BM25Retriever(BaseRetriever):
    name = "bm25"

    def __init__(self, corpus: Corpus, *, k1: float = 1.5, b: float = 0.75):
        super().__init__(corpus)
        self.bm25, self.tokenization = build_bm25_index(corpus, k1=k1, b=b)
        self.params = {"k1": k1, "b": b, "tokenization": self.tokenization}

    def retrieve(self, query: str, k: int = 10,
                 filter_mask: np.ndarray | None = None) -> list[tuple[int, float]]:
        tokens = normalize_text(query).split()
        if not tokens:
            return []
        scores = np.asarray(self.bm25.get_scores(tokens), dtype=float)
        scores = _apply_mask(scores, filter_mask)
        return _topk_from_scores(scores, self.corpus.doc_ids, k, min_score=0.0)


# ---------- Embedding ----------
class EmbeddingRetriever(BaseRetriever):
    name = "embedding"

    def __init__(self, corpus: Corpus, model_name: str = "all-MiniLM-L6-v2"):
        super().__init__(corpus)
        (self.model, self.embeddings), self.model_name = build_embedding_index(
            corpus, model_name=model_name
        )
        self.embedding_dim = int(self.embeddings.shape[1])
        self.params = {
            "model_name": self.model_name,
            "embedding_dim": self.embedding_dim,
            "normalize_embeddings": True,
            "similarity": "cosine",
        }

    def retrieve(self, query: str, k: int = 10,
                 filter_mask: np.ndarray | None = None) -> list[tuple[int, float]]:
        q = self.model.encode(
            [query], normalize_embeddings=True,
            show_progress_bar=False, convert_to_numpy=True,
        )
        sims = (self.embeddings @ q.T).ravel()
        sims = _apply_mask(sims, filter_mask)
        return _topk_from_scores(sims, self.corpus.doc_ids, k, min_score=-np.inf)


# ---------- RRF (hybrid) ----------
class RRFRetriever(BaseRetriever):
    name = "hybrid_rrf"

    def __init__(self, corpus: Corpus, retrievers: list[BaseRetriever],
                 k_rrf: int = 60):
        super().__init__(corpus)
        self.retrievers = retrievers
        self.k_rrf = k_rrf
        self.params = {"k_rrf": k_rrf,
                       "components": [r.name for r in retrievers]}

    def retrieve(self, query: str, k: int = 10,
                 filter_mask: np.ndarray | None = None) -> list[tuple[int, float]]:
        pool_k = max(100, k * 10)
        fused: dict[int, float] = {}
        for r in self.retrievers:
            hits = r.retrieve(query, k=pool_k, filter_mask=filter_mask)
            for rank, (doc_id, _) in enumerate(hits, start=1):
                fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (self.k_rrf + rank)
        ranked = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
        return [(doc_id, float(s)) for doc_id, s in ranked]


# ---------- Intent-conditioned wrapper ----------
class IntentConditionedRetriever(BaseRetriever):
    """Filters the corpus by a target intent before ranking.

    intent_resolver: callable(query_text, *, root_id=None, true_intent=None) -> str
        Returns the intent to filter by. Use oracle resolver for diagnostics,
        classifier resolver for the production pipeline.
    """
    def __init__(self, corpus: Corpus, base: BaseRetriever,
                 intent_resolver, *, name: str = "intent_conditioned"):
        super().__init__(corpus)
        self.base = base
        self.intent_resolver = intent_resolver
        self.name = name

    def retrieve(self, query: str, k: int = 10,
                 filter_mask: np.ndarray | None = None,
                 *, root_id: int | None = None,
                 true_intent: str | None = None) -> list[tuple[int, float]]:
        target = self.intent_resolver(
            query, root_id=root_id, true_intent=true_intent
        )
        intent_mask = (self.corpus.intents == target)
        if filter_mask is not None:
            intent_mask = intent_mask & filter_mask
        if intent_mask.sum() == 0:
            # Fallback: unrestricted retrieval
            return self.base.retrieve(query, k=k, filter_mask=filter_mask)
        return self.base.retrieve(query, k=k, filter_mask=intent_mask)


# ---------- Registry ----------
def build_all_retrievers(corpus: Corpus,
                         embedding_model: str = "all-MiniLM-L6-v2"
                         ) -> dict[str, BaseRetriever]:
    """Return all dev-comparable retrievers keyed by name.
    Callers add intent_conditioned variants separately (they need an
    intent resolver)."""
    tfidf = TFIDFRetriever(corpus)
    bm25  = BM25Retriever(corpus)
    emb   = EmbeddingRetriever(corpus, model_name=embedding_model)
    hybrid = RRFRetriever(corpus, [bm25, emb], k_rrf=60)
    return {
        "tfidf":      tfidf,
        "bm25":       bm25,
        "embedding":  emb,
        "hybrid_rrf": hybrid,
    }