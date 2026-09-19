"""
tests/test_evaluation.py
Tests for the evaluation infrastructure (benchmark.json + evaluator.py).

Design principles:
  - Test evaluator *behaviour*, not hard-coded detector scores.
  - Structural/schema tests guarantee the benchmark stays parseable.
  - Functional tests use synthetic mini-benchmarks so they remain
    independent of the real detector performance.
"""

import json
import math
from pathlib import Path
import sys
import pytest

# Make project importable when running from the app/ directory
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.evaluator import load_benchmark, evaluate, _prf

BENCHMARK_PATH = PROJECT_ROOT / "evaluation" / "benchmark.json"


# ─────────────────────────────────────────────
# 1. Benchmark JSON structure tests
# ─────────────────────────────────────────────

def test_benchmark_loads_without_error():
    """benchmark.json must be valid, parseable JSON."""
    data = load_benchmark(BENCHMARK_PATH)
    assert isinstance(data, list)


def test_benchmark_has_sufficient_samples():
    """Benchmark must contain 40–60 samples."""
    data = load_benchmark(BENCHMARK_PATH)
    assert 40 <= len(data) <= 60, (
        f"Expected 40-60 samples, found {len(data)}"
    )


def test_every_sample_has_text_field():
    """Every sample must contain a 'text' key with a non-empty string."""
    data = load_benchmark(BENCHMARK_PATH)
    for i, sample in enumerate(data):
        assert "text" in sample, f"Sample {i} missing 'text'"
        assert isinstance(sample["text"], str), f"Sample {i} 'text' not a string"
        assert sample["text"].strip(), f"Sample {i} has empty 'text'"


def test_every_sample_has_entities_list():
    """Every sample must contain an 'entities' key that is a list."""
    data = load_benchmark(BENCHMARK_PATH)
    for i, sample in enumerate(data):
        assert "entities" in sample, f"Sample {i} missing 'entities'"
        assert isinstance(sample["entities"], list), (
            f"Sample {i} 'entities' is not a list"
        )


def test_every_entity_has_type_and_value():
    """Every entity object must have 'type' and 'value' string fields."""
    data = load_benchmark(BENCHMARK_PATH)
    for i, sample in enumerate(data):
        for j, entity in enumerate(sample["entities"]):
            assert "type" in entity, (
                f"Sample {i}, entity {j} missing 'type'"
            )
            assert "value" in entity, (
                f"Sample {i}, entity {j} missing 'value'"
            )
            assert isinstance(entity["type"], str), (
                f"Sample {i}, entity {j}: 'type' must be a string"
            )
            assert isinstance(entity["value"], str), (
                f"Sample {i}, entity {j}: 'value' must be a string"
            )


def test_entity_types_are_known():
    """Every entity type in the benchmark must be a recognised PII type."""
    KNOWN_TYPES = {
        "NAME", "EMAIL", "PHONE", "PAN", "CARD",
        "ACCOUNT", "IP", "URL", "API_KEY", "JWT",
    }
    data = load_benchmark(BENCHMARK_PATH)
    for i, sample in enumerate(data):
        for j, entity in enumerate(sample["entities"]):
            assert entity["type"] in KNOWN_TYPES, (
                f"Sample {i}, entity {j}: unknown type '{entity['type']}'"
            )


def test_benchmark_covers_multiple_entity_types():
    """Benchmark must cover at least 8 of the 10 PII entity types."""
    data = load_benchmark(BENCHMARK_PATH)
    found_types = {
        e["type"]
        for sample in data
        for e in sample["entities"]
    }
    assert len(found_types) >= 8, (
        f"Only {len(found_types)} entity types covered: {found_types}"
    )


def test_benchmark_contains_negative_samples():
    """At least 5 samples must be clean (empty entities list)."""
    data = load_benchmark(BENCHMARK_PATH)
    negatives = [s for s in data if not s.get("entities")]
    assert len(negatives) >= 5, (
        f"Expected at least 5 negative samples, found {len(negatives)}"
    )


# ─────────────────────────────────────────────
# 2. _prf helper function tests
# ─────────────────────────────────────────────

def test_prf_perfect():
    p, r, f = _prf(tp=10, fp=0, fn=0)
    assert p == 1.0
    assert r == 1.0
    assert f == 1.0


def test_prf_zero_detection():
    """When nothing is detected, precision is undefined → 0; recall is 0."""
    p, r, f = _prf(tp=0, fp=0, fn=5)
    assert p == 0.0
    assert r == 0.0
    assert f == 0.0


def test_prf_all_false_positives():
    """When all detections are wrong, recall is 0; precision is 0."""
    p, r, f = _prf(tp=0, fp=5, fn=0)
    assert p == 0.0
    assert r == 0.0
    assert f == 0.0


def test_prf_balanced():
    p, r, f = _prf(tp=8, fp=2, fn=2)
    assert abs(p - 0.8) < 1e-3
    assert abs(r - 0.8) < 1e-3
    assert abs(f - 0.8) < 1e-3


def test_prf_f1_harmonic_mean():
    """F1 = 2·P·R / (P + R)."""
    p, r, f = _prf(tp=3, fp=1, fn=1)
    expected_p = 3 / 4
    expected_r = 3 / 4
    expected_f = 2 * expected_p * expected_r / (expected_p + expected_r)
    assert abs(f - expected_f) < 1e-3


# ─────────────────────────────────────────────
# 3. evaluate() output schema tests
# ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def eval_results():
    """Run the real evaluator once for all output-schema tests."""
    data = load_benchmark(BENCHMARK_PATH)
    return evaluate(data)


def test_evaluate_returns_required_keys(eval_results):
    required = {
        "total_samples", "total_expected", "total_detected",
        "true_positive", "false_positive", "false_negative",
        "precision", "recall", "f1",
        "total_time_s", "avg_latency_ms",
        "per_type", "mismatches",
    }
    assert required.issubset(eval_results.keys())


def test_evaluate_counts_are_non_negative(eval_results):
    for key in ("total_samples", "total_expected", "total_detected",
                "true_positive", "false_positive", "false_negative"):
        assert eval_results[key] >= 0, f"{key} is negative"


def test_evaluate_metrics_in_unit_interval(eval_results):
    for metric in ("precision", "recall", "f1"):
        val = eval_results[metric]
        assert 0.0 <= val <= 1.0, f"{metric}={val} out of [0, 1]"


def test_evaluate_latency_positive(eval_results):
    assert eval_results["total_time_s"] >= 0
    assert eval_results["avg_latency_ms"] >= 0


def test_evaluate_total_samples_matches_benchmark(eval_results):
    data = load_benchmark(BENCHMARK_PATH)
    assert eval_results["total_samples"] == len(data)


def test_evaluate_per_type_structure(eval_results):
    """per_type must map type-strings → dicts with tp/fp/fn/precision/recall/f1."""
    for etype, m in eval_results["per_type"].items():
        for field in ("tp", "fp", "fn", "precision", "recall", "f1"):
            assert field in m, f"per_type[{etype}] missing '{field}'"


def test_evaluate_mismatches_is_list(eval_results):
    assert isinstance(eval_results["mismatches"], list)


# ─────────────────────────────────────────────
# 4. Synthetic mini-benchmark tests
# ─────────────────────────────────────────────

def _make_sample(text, *type_value_pairs):
    return {
        "text": text,
        "entities": [{"type": t, "value": v} for t, v in type_value_pairs],
    }


def test_evaluate_clean_sample_no_fp():
    """A truly clean sentence should not produce false positives."""
    clean = _make_sample("The bank is open from 9 AM to 5 PM.")
    results = evaluate([clean])
    assert results["false_positive"] == 0
    assert results["false_negative"] == 0
    assert results["true_positive"] == 0


def test_evaluate_clear_email_tp():
    """A direct email address must be detected as a true positive."""
    sample = _make_sample("Email support@example.com for help.", ("EMAIL", "support@example.com"))
    results = evaluate([sample])
    assert results["true_positive"] >= 1


def test_evaluate_precision_recall_consistency():
    """TP / (TP + FP) and TP / (TP + FN) must equal reported P and R."""
    data = load_benchmark(BENCHMARK_PATH)
    results = evaluate(data)

    tp, fp, fn = results["true_positive"], results["false_positive"], results["false_negative"]
    expected_p = tp / (tp + fp) if tp + fp else 0.0
    expected_r = tp / (tp + fn) if tp + fn else 0.0

    assert abs(results["precision"] - expected_p) < 1e-4
    assert abs(results["recall"] - expected_r) < 1e-4


def test_evaluate_f1_formula():
    """F1 must equal the harmonic mean of precision and recall."""
    data = load_benchmark(BENCHMARK_PATH)
    results = evaluate(data)
    p, r = results["precision"], results["recall"]
    if p + r > 0:
        expected_f1 = 2 * p * r / (p + r)
    else:
        expected_f1 = 0.0
    assert abs(results["f1"] - expected_f1) < 1e-4
