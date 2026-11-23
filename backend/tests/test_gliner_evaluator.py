"""
Tests for GLiNER evaluator infrastructure and benchmark schema.
"""

from pathlib import Path
import sys
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.gliner_evaluator import (
    BENCHMARK_LABELS,
    LABEL_MAPPING,
    calculate_prf,
    evaluate,
    format_report,
    load_benchmark,
)

GLINER_BENCHMARK_PATH = PROJECT_ROOT / "evaluation" / "gliner_benchmark.json"


def test_gliner_benchmark_loads_and_has_30_samples():
    """gliner_benchmark.json must load cleanly and contain 30 samples."""
    samples = load_benchmark(GLINER_BENCHMARK_PATH)
    assert isinstance(samples, list)
    assert len(samples) == 30


def test_gliner_benchmark_schema():
    """All samples must adhere to the required GLiNER benchmark schema."""
    samples = load_benchmark(GLINER_BENCHMARK_PATH)
    for sample in samples:
        assert "id" in sample and isinstance(sample["id"], str)
        assert "text" in sample and isinstance(sample["text"], str)
        assert "entities" in sample and isinstance(sample["entities"], list)
        for ent in sample["entities"]:
            assert "text" in ent and isinstance(ent["text"], str)
            assert "label" in ent and isinstance(ent["label"], str)
            assert ent["label"] in BENCHMARK_LABELS, f"Unknown label: {ent['label']}"
            assert ent["text"] in sample["text"], f"Span '{ent['text']}' not in sample text"


def test_gliner_label_mapping_covers_all_benchmark_labels():
    """LABEL_MAPPING must map all benchmark labels to expected canonical types."""
    expected_canonical_types = {
        "NAME",
        "EMAIL",
        "PHONE",
        "PAN",
        "CARD",
        "ACCOUNT",
        "IP",
        "URL",
        "API_KEY",
        "JWT",
    }
    mapped_types = set(LABEL_MAPPING.values())
    assert mapped_types == expected_canonical_types
    for label in BENCHMARK_LABELS:
        assert label in LABEL_MAPPING


def test_calculate_prf_metric_calculations():
    """Test precision, recall, and F1 calculations including zero-division handling."""
    # Zero counts
    assert calculate_prf(0, 0, 0) == (0.0, 0.0, 0.0)
    # Perfect score
    assert calculate_prf(10, 0, 0) == (1.0, 1.0, 1.0)
    # FP only
    assert calculate_prf(0, 5, 5) == (0.0, 0.0, 0.0)
    # Balanced
    p, r, f = calculate_prf(5, 5, 5)
    assert p == 0.5
    assert r == 0.5
    assert f == 0.5


class MockGLiNER:
    """Mock model to test evaluation pipeline logic without invoking GPU."""

    def __init__(self, canned_predictions):
        self.canned_predictions = canned_predictions

    def predict_entities(self, text, labels, **kwargs):
        return self.canned_predictions.get(text, [])


def test_evaluator_pipeline_with_mock():
    """Test evaluation calculation logic and mismatch reporting with synthetic samples."""
    mock_benchmark = [
        {
            "id": "mock_001",
            "category": "test",
            "text": "Call Alice at 9876543210",
            "entities": [
                {"text": "Alice", "label": "NAME"},
                {"text": "9876543210", "label": "PHONE"},
            ],
        },
        {
            "id": "mock_002",
            "category": "negative",
            "text": "Just plain text without sensitive data",
            "entities": [],
        },
    ]

    mock_preds = {
        "Call Alice at 9876543210": [
            {"text": "Alice", "label": "NAME", "score": 0.95},
            {"text": "9876543210", "label": "PHONE", "score": 0.92},
        ],
        "Just plain text without sensitive data": [
            {"text": "sensitive data", "label": "API KEY", "score": 0.60},
        ],
    }

    mock_model = MockGLiNER(mock_preds)
    results = evaluate(benchmark=mock_benchmark, model=mock_model, device="mock")

    assert results["total_samples"] == 2
    assert results["total_expected_entities"] == 2
    assert results["total_predicted_entities"] == 3
    assert results["tp"] == 2
    assert results["fp"] == 1
    assert results["fn"] == 0
    assert results["precision"] == round(2 / 3, 4)
    assert results["recall"] == 1.0
    assert len(results["mismatches"]) == 1
    assert results["mismatches"][0]["id"] == "mock_002"

    report = format_report(results)
    assert "GLiNER BENCHMARK EVALUATION REPORT" in report
    assert "mock_002" in report
