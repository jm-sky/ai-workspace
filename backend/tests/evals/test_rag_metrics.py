"""Tests for the dependency-free RAG eval metrics."""

from evals.rag.metrics import (
    aggregate,
    context_precision,
    context_recall,
    hit_rate,
    mean_reciprocal_rank,
    score_question,
)


def test_hit_rate_true_when_relevant_doc_present():
    assert hit_rate(["a", "b", "c"], ["c"]) == 1.0


def test_hit_rate_false_when_no_overlap():
    assert hit_rate(["a", "b"], ["z"]) == 0.0


def test_mrr_rewards_earlier_rank():
    assert mean_reciprocal_rank(["a", "b", "c"], ["a"]) == 1.0
    assert mean_reciprocal_rank(["a", "b", "c"], ["b"]) == 0.5
    assert mean_reciprocal_rank(["a", "b", "c"], ["c"]) == 1 / 3


def test_mrr_zero_when_not_found():
    assert mean_reciprocal_rank(["a", "b"], ["z"]) == 0.0


def test_context_precision_fraction_relevant():
    assert context_precision(["a", "b", "c", "d"], ["a", "c"]) == 0.5


def test_context_precision_empty_retrieval_is_zero():
    assert context_precision([], ["a"]) == 0.0


def test_context_recall_fraction_of_relevant_found():
    assert context_recall(["a", "x", "y"], ["a", "b"]) == 0.5


def test_context_recall_vacuously_true_with_no_relevant_docs():
    assert context_recall(["a"], []) == 1.0


def test_score_question_bundles_all_four_metrics():
    result = score_question(["a", "b"], ["a"])
    assert result.hit_rate == 1.0
    assert result.mrr == 1.0
    assert result.context_precision == 0.5
    assert result.context_recall == 1.0


def test_aggregate_averages_across_questions():
    results = [
        score_question(["a"], ["a"]),  # all metrics 1.0
        score_question(["x"], ["a"]),  # all metrics 0.0
    ]
    avg = aggregate(results)
    assert avg.hit_rate == 0.5
    assert avg.mrr == 0.5
    assert avg.context_precision == 0.5
    assert avg.context_recall == 0.5


def test_aggregate_empty_returns_zeros():
    avg = aggregate([])
    assert avg.hit_rate == 0.0
    assert avg.context_recall == 0.0
