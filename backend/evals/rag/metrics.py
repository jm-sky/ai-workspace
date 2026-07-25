"""Retrieval-quality metrics for the RAG eval harness.

Dependency-free, deterministic re-implementations of the four RAGAS-style
metrics we can compute without an LLM judge (context precision/recall need
ground-truth relevant documents, not generated answers). No live model call
required — safe to unit test with synthetic data.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalMetrics:
    hit_rate: float
    mrr: float
    context_precision: float
    context_recall: float


def hit_rate(retrieved_docs: list[str], relevant_docs: list[str]) -> float:
    """1.0 if any relevant doc appears anywhere in the retrieved list, else 0.0."""
    relevant = set(relevant_docs)
    return 1.0 if any(doc in relevant for doc in retrieved_docs) else 0.0


def mean_reciprocal_rank(retrieved_docs: list[str], relevant_docs: list[str]) -> float:
    """1/rank of the first relevant hit (1-indexed); 0.0 if none found."""
    relevant = set(relevant_docs)
    for rank, doc in enumerate(retrieved_docs, start=1):
        if doc in relevant:
            return 1.0 / rank
    return 0.0


def context_precision(retrieved_docs: list[str], relevant_docs: list[str]) -> float:
    """Fraction of retrieved results that are actually relevant."""
    if not retrieved_docs:
        return 0.0
    relevant = set(relevant_docs)
    hits = sum(1 for doc in retrieved_docs if doc in relevant)
    return hits / len(retrieved_docs)


def context_recall(retrieved_docs: list[str], relevant_docs: list[str]) -> float:
    """Fraction of the known-relevant docs that were found anywhere in retrieval."""
    if not relevant_docs:
        return 1.0
    retrieved = set(retrieved_docs)
    found = sum(1 for doc in set(relevant_docs) if doc in retrieved)
    return found / len(set(relevant_docs))


def score_question(retrieved_docs: list[str], relevant_docs: list[str]) -> RetrievalMetrics:
    return RetrievalMetrics(
        hit_rate=hit_rate(retrieved_docs, relevant_docs),
        mrr=mean_reciprocal_rank(retrieved_docs, relevant_docs),
        context_precision=context_precision(retrieved_docs, relevant_docs),
        context_recall=context_recall(retrieved_docs, relevant_docs),
    )


def aggregate(per_question: list[RetrievalMetrics]) -> RetrievalMetrics:
    """Mean of each metric across all questions."""
    if not per_question:
        return RetrievalMetrics(hit_rate=0.0, mrr=0.0, context_precision=0.0, context_recall=0.0)
    n = len(per_question)
    return RetrievalMetrics(
        hit_rate=sum(m.hit_rate for m in per_question) / n,
        mrr=sum(m.mrr for m in per_question) / n,
        context_precision=sum(m.context_precision for m in per_question) / n,
        context_recall=sum(m.context_recall for m in per_question) / n,
    )
