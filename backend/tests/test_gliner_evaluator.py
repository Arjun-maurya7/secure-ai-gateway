"""
Tests for GLiNER evaluator infrastructure and benchmark schema.
"""

from pathlib import Path
import sys
from unittest.mock import patch, MagicMock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.gliner_evaluator import (
    BENCHMARK_LABELS,
    DEFAULT_ADAPTER,
    DEFAULT_MODEL_NAME,
    GRETEL_ADAPTER,
    LABEL_MAPPING,
    ModelLabelAdapter,
    calculate_prf,
    evaluate,
    format_report,
    get_adapter,
    load_benchmark,
    parse_args,
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
        self.last_labels_passed = None

    def predict_entities(self, text, labels, **kwargs):
        self.last_labels_passed = labels
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
    assert results["model_name"] == DEFAULT_MODEL_NAME
    assert f"Model       : {DEFAULT_MODEL_NAME}" in report


def test_default_model_name_unchanged():
    """DEFAULT_MODEL_NAME must remain urchade/gliner_multi_pii-v1."""
    assert DEFAULT_MODEL_NAME == "urchade/gliner_multi_pii-v1"


def test_evaluate_default_model_reported_with_mock():
    """evaluate() should report DEFAULT_MODEL_NAME when model_name is not provided."""
    mock_model = MockGLiNER({})
    results = evaluate(benchmark=[], model=mock_model, device="mock")
    assert results["model_name"] == DEFAULT_MODEL_NAME
    assert results["model_name"] == "urchade/gliner_multi_pii-v1"


def test_evaluate_custom_model_name_passed_to_loader():
    """evaluate() should pass custom model_name to load_gliner_model when model is None."""
    custom_model_name = "urchade/gliner_small-v2.1"
    mock_model = MockGLiNER({})
    with patch("evaluation.gliner_evaluator.load_gliner_model") as mock_loader:
        mock_loader.return_value = (mock_model, "cpu")
        results = evaluate(benchmark=[], model_name=custom_model_name)
        mock_loader.assert_called_once_with(model_name=custom_model_name, device=None)
        assert results["model_name"] == custom_model_name


def test_evaluate_custom_model_name_reported_with_provided_model():
    """evaluate() should report custom model_name and avoid calling loader when model is provided."""
    custom_model_name = "urchade/gliner_base-v2.1"
    mock_model = MockGLiNER({})
    with patch("evaluation.gliner_evaluator.load_gliner_model") as mock_loader:
        results = evaluate(
            benchmark=[],
            model=mock_model,
            model_name=custom_model_name,
            device="mock",
        )
        mock_loader.assert_not_called()
        assert results["model_name"] == custom_model_name


def test_parse_args_cli_selection():
    """CLI argument parser should handle default and custom --model selections."""
    default_args = parse_args([])
    assert default_args.model_name == DEFAULT_MODEL_NAME
    assert default_args.adapter_name is None

    custom_args = parse_args(["--model", "urchade/gliner_medium-v2.1", "--adapter", "gretel"])
    assert custom_args.model_name == "urchade/gliner_medium-v2.1"
    assert custom_args.adapter_name == "gretel"


def test_adapter_selection_by_model_id():
    """Verify correct adapter selection by model ID and registry name."""
    assert get_adapter("urchade/gliner_multi_pii-v1").name == "default"
    assert get_adapter("knowledgator/gliner-pii-small-v1.0").name == "default"
    assert get_adapter("gretelai/gretel-gliner-bi-small-v1.0").name == "gretel"
    assert get_adapter("default").name == "default"
    assert get_adapter("gretel").name == "gretel"
    assert get_adapter(None).name == "default"


def test_adapter_unknown_model_handling():
    """Verify unknown model IDs fall back to default or fail clearly with strict=True."""
    # Default fallback behavior
    fallback_adapter = get_adapter("unknown/unregistered-model")
    assert fallback_adapter.name == "default"
    assert fallback_adapter.prompt_labels == BENCHMARK_LABELS

    # Strict error behavior
    with pytest.raises(ValueError, match="Unknown model or adapter identifier"):
        get_adapter("unknown/unregistered-model", strict=True)


def test_gretel_adapter_prompt_labels_and_prediction_mapping():
    """Verify Gretel candidate prompt labels and canonical mappings."""
    expected_prompt_labels = [
        "NAME",
        "EMAIL",
        "phone_number",
        "PAN",
        "credit_card_number",
        "account_number",
        "ipv4",
        "URL",
        "api_key",
        "JWT",
    ]
    assert GRETEL_ADAPTER.prompt_labels == expected_prompt_labels

    # Verify model predicted labels map back to canonical benchmark entity types
    assert GRETEL_ADAPTER.map_prediction("phone_number") == "PHONE"
    assert GRETEL_ADAPTER.map_prediction("credit_card_number") == "CARD"
    assert GRETEL_ADAPTER.map_prediction("account_number") == "ACCOUNT"
    assert GRETEL_ADAPTER.map_prediction("ipv4") == "IP"
    assert GRETEL_ADAPTER.map_prediction("api_key") == "API_KEY"
    assert GRETEL_ADAPTER.map_prediction("NAME") == "NAME"
    assert GRETEL_ADAPTER.map_prediction("EMAIL") == "EMAIL"
    assert GRETEL_ADAPTER.map_prediction("PAN") == "PAN"
    assert GRETEL_ADAPTER.map_prediction("URL") == "URL"
    assert GRETEL_ADAPTER.map_prediction("JWT") == "JWT"
    # Unmapped label returns as-is
    assert GRETEL_ADAPTER.map_prediction("custom_unknown_label") == "custom_unknown_label"


def test_evaluate_passes_correct_prompt_labels_to_model():
    """evaluate() should pass model-specific prompt labels based on the selected adapter."""
    mock_model = MockGLiNER({})
    sample_benchmark = [{"id": "s1", "text": "Contact info at test@example.com", "entities": []}]

    # Gretel model should receive Gretel candidate prompt labels
    evaluate(
        benchmark=sample_benchmark,
        model=mock_model,
        model_name="gretelai/gretel-gliner-bi-small-v1.0",
        device="mock",
    )
    assert mock_model.last_labels_passed == GRETEL_ADAPTER.prompt_labels

    # Default model should receive default benchmark labels
    evaluate(
        benchmark=sample_benchmark,
        model=mock_model,
        model_name="urchade/gliner_multi_pii-v1",
        device="mock",
    )
    assert mock_model.last_labels_passed == BENCHMARK_LABELS


def test_evaluate_gretel_adapter_end_to_end_mapping():
    """evaluate() with Gretel adapter maps predicted snake_case labels to benchmark canonical types."""
    mock_benchmark = [
        {
            "id": "gretel_mock_001",
            "category": "test",
            "text": "Transfer from account 987654321 to card 4111222233334444. Call +91 9876543210 at 10.0.0.1 with key sk-test-key.",
            "entities": [
                {"text": "987654321", "label": "BANK ACCOUNT NUMBER"},
                {"text": "4111222233334444", "label": "CREDIT CARD"},
                {"text": "+91 9876543210", "label": "PHONE"},
                {"text": "10.0.0.1", "label": "IP ADDRESS"},
                {"text": "sk-test-key", "label": "API KEY"},
            ],
        }
    ]

    # Mock predictions returned by Gretel model using Gretel's candidate prompt labels
    mock_preds = {
        mock_benchmark[0]["text"]: [
            {"text": "987654321", "label": "account_number", "score": 0.95},
            {"text": "4111222233334444", "label": "credit_card_number", "score": 0.94},
            {"text": "+91 9876543210", "label": "phone_number", "score": 0.93},
            {"text": "10.0.0.1", "label": "ipv4", "score": 0.91},
            {"text": "sk-test-key", "label": "api_key", "score": 0.96},
        ]
    }

    mock_model = MockGLiNER(mock_preds)
    results = evaluate(
        benchmark=mock_benchmark,
        model=mock_model,
        model_name="gretelai/gretel-gliner-bi-small-v1.0",
        device="mock",
    )

    # All 5 entities should successfully match expected canonical types
    assert results["adapter"] == "gretel"
    assert results["total_samples"] == 1
    assert results["total_expected_entities"] == 5
    assert results["total_predicted_entities"] == 5
    assert results["tp"] == 5
    assert results["fp"] == 0
    assert results["fn"] == 0
    assert results["precision"] == 1.0
    assert results["recall"] == 1.0
    assert len(results["mismatches"]) == 0

    # Verify per-type canonical metrics
    assert results["per_type"]["ACCOUNT"]["tp"] == 1
    assert results["per_type"]["CARD"]["tp"] == 1
    assert results["per_type"]["PHONE"]["tp"] == 1
    assert results["per_type"]["IP"]["tp"] == 1
    assert results["per_type"]["API_KEY"]["tp"] == 1
