"""
Tests for isolated GLiNER threshold sweep experiment utility.
"""

import csv
import json
from pathlib import Path
import sys
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.threshold_sweep import (
    DEFAULT_THRESHOLDS,
    SWEEP_MODELS,
    measure_inference_latency,
    run_threshold_sweep,
    save_results,
    format_comparison_table,
)
from evaluation.gliner_evaluator import (
    DEFAULT_ADAPTER,
    GRETEL_ADAPTER,
    BENCHMARK_LABELS,
)


class MockThresholdModel:
    """Mock GLiNER model that filters predictions by score against confidence threshold."""

    def __init__(self, text_predictions):
        self.text_predictions = text_predictions
        self.last_labels_passed = None
        self.call_count = 0

    def predict_entities(self, text, labels, threshold=0.5, **kwargs):
        self.last_labels_passed = labels
        self.call_count += 1
        raw_items = self.text_predictions.get(text, [])
        return [item for item in raw_items if item.get("score", 0.0) >= threshold]


def test_default_thresholds_and_models_configuration():
    """Verify default sweep configuration has 5 thresholds and 3 models."""
    assert DEFAULT_THRESHOLDS == [0.30, 0.40, 0.50, 0.60, 0.70]
    assert len(SWEEP_MODELS) == 3
    assert SWEEP_MODELS[0]["model_name"] == "urchade/gliner_multi_pii-v1"
    assert SWEEP_MODELS[0]["adapter_name"] == "default"
    assert SWEEP_MODELS[1]["model_name"] == "knowledgator/gliner-pii-small-v1.0"
    assert SWEEP_MODELS[1]["adapter_name"] == "default"
    assert SWEEP_MODELS[2]["model_name"] == "gretelai/gretel-gliner-bi-small-v1.0"
    assert SWEEP_MODELS[2]["adapter_name"] == "gretel"


def test_measure_inference_latency_mock():
    """Verify latency measurement executes warmup and timed passes with mock model."""
    mock_model = MockThresholdModel({"sample text": []})
    samples = [{"id": "s1", "text": "sample text", "entities": []}]
    prompt_labels = ["NAME", "EMAIL"]

    stats = measure_inference_latency(
        model=mock_model,
        samples=samples,
        prompt_labels=prompt_labels,
        device="cpu",
        warmup_passes=1,
        timed_passes=3,
    )

    assert "warmup_time_s" in stats
    assert "measured_time_s" in stats
    assert stats["timed_passes"] == 3
    assert stats["avg_latency_ms"] >= 0.0
    # 1 warmup + 3 timed = 4 predict_entities calls
    assert mock_model.call_count == 4


def test_threshold_filtering_and_metrics_calculation(tmp_path):
    """Verify that predictions filter properly across all 5 thresholds and compute metrics."""
    test_text = "Alice email alice@test.com card 4111222233334444 account 123456789 phone 9876543210"
    mock_benchmark = [
        {
            "id": "t_001",
            "category": "test",
            "text": test_text,
            "entities": [
                {"text": "Alice", "label": "NAME"},
                {"text": "alice@test.com", "label": "EMAIL"},
                {"text": "4111222233334444", "label": "CREDIT CARD"},
                {"text": "123456789", "label": "BANK ACCOUNT NUMBER"},
                {"text": "9876543210", "label": "PHONE"},
            ],
        }
    ]

    # Predictions with varying confidence scores
    mock_preds = {
        test_text: [
            {"text": "Alice", "label": "NAME", "score": 0.75},              # passes all (>=0.3 to >=0.7)
            {"text": "alice@test.com", "label": "EMAIL", "score": 0.65},     # passes <=0.60
            {"text": "4111222233334444", "label": "CREDIT CARD", "score": 0.55}, # passes <=0.50
            {"text": "123456789", "label": "BANK ACCOUNT NUMBER", "score": 0.45}, # passes <=0.40
            {"text": "9876543210", "label": "PHONE", "score": 0.35},        # passes only 0.30
        ]
    }

    mock_model = MockThresholdModel(mock_preds)

    def mock_loader(model_name):
        return mock_model, "mock"

    models_config = [{"model_name": "mock/model", "adapter_name": "default"}]
    thresholds = [0.30, 0.40, 0.50, 0.60, 0.70]

    sweep_results = run_threshold_sweep(
        models_config=models_config,
        thresholds=thresholds,
        benchmark=mock_benchmark,
        model_loader=mock_loader,
        results_dir=tmp_path,
        save_files=True,
        measure_latency=False,
    )

    records = sweep_results["records"]
    assert len(records) == 5

    # Check predicted counts decay as threshold increases: 5, 4, 3, 2, 1
    expected_tps = [5, 4, 3, 2, 1]
    for i, t in enumerate(thresholds):
        r = records[i]
        assert r["threshold"] == t
        assert r["expected_entities"] == 5
        assert r["predicted_entities"] == expected_tps[i]
        assert r["tp"] == expected_tps[i]
        assert r["fp"] == 0
        assert r["fn"] == 5 - expected_tps[i]
        assert r["precision"] == 1.0
        assert r["recall"] == round(expected_tps[i] / 5, 4)


def test_model_adapter_and_canonical_mapping_in_sweep(tmp_path):
    """Verify Gretel and Default adapters select appropriate prompt labels and map to canonical types."""
    test_text = "Call 9876543210 and card 4111222233334444"
    mock_benchmark = [
        {
            "id": "t_002",
            "category": "test",
            "text": test_text,
            "entities": [
                {"text": "9876543210", "label": "PHONE"},
                {"text": "4111222233334444", "label": "CREDIT CARD"},
            ],
        }
    ]

    # Gretel returns snake_case labels
    gretel_preds = {
        test_text: [
            {"text": "9876543210", "label": "phone_number", "score": 0.85},
            {"text": "4111222233334444", "label": "credit_card_number", "score": 0.82},
        ]
    }
    # Default returns uppercase labels
    default_preds = {
        test_text: [
            {"text": "9876543210", "label": "PHONE", "score": 0.85},
            {"text": "4111222233334444", "label": "CREDIT CARD", "score": 0.82},
        ]
    }

    gretel_mock = MockThresholdModel(gretel_preds)
    default_mock = MockThresholdModel(default_preds)

    def mock_loader(model_name):
        if "gretel" in model_name:
            return gretel_mock, "mock"
        return default_mock, "mock"

    models_config = [
        {"model_name": "urchade/gliner_multi_pii-v1", "adapter_name": "default"},
        {"model_name": "gretelai/gretel-gliner-bi-small-v1.0", "adapter_name": "gretel"},
    ]

    sweep_results = run_threshold_sweep(
        models_config=models_config,
        thresholds=[0.50],
        benchmark=mock_benchmark,
        model_loader=mock_loader,
        results_dir=tmp_path,
        save_files=False,
        measure_latency=False,
    )

    records = sweep_results["records"]
    assert len(records) == 2

    # Verify Default adapter
    r_default = records[0]
    assert r_default["adapter"] == "default"
    assert r_default["tp"] == 2
    assert r_default["precision"] == 1.0
    assert default_mock.last_labels_passed == BENCHMARK_LABELS

    # Verify Gretel adapter
    r_gretel = records[1]
    assert r_gretel["adapter"] == "gretel"
    assert r_gretel["tp"] == 2
    assert r_gretel["precision"] == 1.0
    assert gretel_mock.last_labels_passed == GRETEL_ADAPTER.prompt_labels


def test_output_csv_and_json_structure(tmp_path):
    """Verify saved CSV and JSON files match expected schema and row counts."""
    mock_benchmark = [{"id": "s1", "text": "Hello world", "entities": []}]
    mock_model = MockThresholdModel({"Hello world": []})

    def mock_loader(model_name):
        return mock_model, "mock"

    sweep_results = run_threshold_sweep(
        models_config=SWEEP_MODELS,
        thresholds=DEFAULT_THRESHOLDS,
        benchmark=mock_benchmark,
        model_loader=mock_loader,
        results_dir=tmp_path,
        save_files=True,
        measure_latency=False,
    )

    csv_path = tmp_path / "threshold_sweep_summary.csv"
    json_path = tmp_path / "threshold_sweep_detailed.json"

    assert csv_path.exists()
    assert json_path.exists()

    # Check CSV rows: header + (3 models * 5 thresholds = 15 rows)
    with open(csv_path, encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 15
        expected_cols = {
            "model_name", "adapter", "threshold", "tp", "fp", "fn",
            "precision", "recall", "f1", "expected_entities", "predicted_entities", "latency_ms"
        }
        assert set(reader[0].keys()) == expected_cols

    # Check JSON structure
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
        assert "metadata" in data
        assert "records" in data
        assert "latency_summary" in data
        assert len(data["records"]) == 15
        assert data["metadata"]["thresholds_evaluated"] == DEFAULT_THRESHOLDS
        assert len(data["metadata"]["models_evaluated"]) == 3

    # Check terminal table formatting
    table = format_comparison_table(sweep_results["records"])
    assert "urchade" in table
    assert "knowledgator" in table
    assert "gretel" in table
