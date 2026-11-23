"""
GLiNER Benchmark Evaluator.

Evaluates urchade/gliner_multi_pii-v1 against backend/evaluation/gliner_benchmark.json.
Independent of DetectionEngine — calls GLiNER directly.
"""

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
from gliner import GLiNER

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Benchmark labels exactly as written in gliner_benchmark.json
BENCHMARK_LABELS: List[str] = [
    "NAME",
    "EMAIL",
    "PHONE",
    "PAN",
    "CREDIT CARD",
    "BANK ACCOUNT NUMBER",
    "IP ADDRESS",
    "URL",
    "API KEY",
    "JWT",
]

# Canonical entity type mapping applied inside the evaluator
LABEL_MAPPING: Dict[str, str] = {
    "NAME": "NAME",
    "EMAIL": "EMAIL",
    "PHONE": "PHONE",
    "PAN": "PAN",
    "CREDIT CARD": "CARD",
    "BANK ACCOUNT NUMBER": "ACCOUNT",
    "IP ADDRESS": "IP",
    "URL": "URL",
    "API KEY": "API_KEY",
    "JWT": "JWT",
}

DEFAULT_BENCHMARK_PATH = Path(__file__).parent / "gliner_benchmark.json"
DEFAULT_MODEL_NAME = "urchade/gliner_multi_pii-v1"


def load_benchmark(path: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """Load the benchmark dataset from JSON."""
    benchmark_file = Path(path) if path else DEFAULT_BENCHMARK_PATH
    with open(benchmark_file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_gliner_model(
    model_name: str = DEFAULT_MODEL_NAME,
    device: Optional[str] = None,
) -> Tuple[GLiNER, str]:
    """Load GLiNER model on CUDA if available, otherwise CPU."""
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model = GLiNER.from_pretrained(model_name).to(device)
    return model, device


def calculate_prf(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    """Calculate Precision, Recall, and F1 score."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)


def evaluate(
    benchmark: Optional[List[Dict[str, Any]]] = None,
    model: Optional[GLiNER] = None,
    device: Optional[str] = None,
    threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """Run GLiNER predictions against every benchmark sample and compute metrics.

    Args:
        benchmark: List of sample dictionaries from gliner_benchmark.json.
        model: Optional pre-loaded GLiNER instance.
        device: Device to use ('cuda' or 'cpu').
        threshold: Optional confidence threshold passed to GLiNER. If None, uses GLiNER default.

    Returns:
        Comprehensive dictionary of evaluation results.
    """
    if benchmark is None:
        benchmark = load_benchmark()

    if model is None:
        model, device = load_gliner_model(device=device)
    elif device is None:
        device = next(model.parameters()).device.type

    total_samples = len(benchmark)
    total_expected_entities = 0
    total_predicted_entities = 0

    overall_tp = 0
    overall_fp = 0
    overall_fn = 0

    per_type: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"expected": 0, "predicted": 0, "tp": 0, "fp": 0, "fn": 0}
    )

    # Initialize all mapped canonical types in per_type so all 10 appear in report
    for canonical_type in LABEL_MAPPING.values():
        _ = per_type[canonical_type]

    mismatches: List[Dict[str, Any]] = []
    sample_results: List[Dict[str, Any]] = []
    total_inference_time_s = 0.0

    predict_kwargs = {}
    if threshold is not None:
        predict_kwargs["threshold"] = threshold

    for sample in benchmark:
        sample_id = sample.get("id", "unknown")
        category = sample.get("category", "")
        text = sample["text"]
        expected_raw = sample.get("entities", [])

        # Map expected entities to (canonical_type, text_span)
        expected_set = {
            (LABEL_MAPPING.get(e["label"], e["label"]), e["text"].strip())
            for e in expected_raw
        }

        # GLiNER inference with latency tracking
        t0 = time.perf_counter()
        raw_predictions = model.predict_entities(text, BENCHMARK_LABELS, **predict_kwargs)
        elapsed = time.perf_counter() - t0
        total_inference_time_s += elapsed

        # Map predicted entities to (canonical_type, text_span)
        predicted_items = [
            {
                "raw_label": p["label"],
                "canonical_type": LABEL_MAPPING.get(p["label"], p["label"]),
                "text": p["text"].strip(),
                "score": round(float(p.get("score", 0.0)), 4),
                "start": p.get("start"),
                "end": p.get("end"),
            }
            for p in raw_predictions
        ]

        predicted_set = {(p["canonical_type"], p["text"]) for p in predicted_items}

        total_expected_entities += len(expected_set)
        total_predicted_entities += len(predicted_set)

        tp_set = expected_set & predicted_set
        fp_set = predicted_set - expected_set
        fn_set = expected_set - predicted_set

        tp = len(tp_set)
        fp = len(fp_set)
        fn = len(fn_set)

        overall_tp += tp
        overall_fp += fp
        overall_fn += fn

        # Per-type counts
        for etype, _ in expected_set:
            per_type[etype]["expected"] += 1
        for ptype, _ in predicted_set:
            per_type[ptype]["predicted"] += 1
        for etype, _ in tp_set:
            per_type[etype]["tp"] += 1
        for ptype, _ in fp_set:
            per_type[ptype]["fp"] += 1
        for etype, _ in fn_set:
            per_type[etype]["fn"] += 1

        sample_detail = {
            "id": sample_id,
            "category": category,
            "text": text,
            "expected": sorted(list(expected_set)),
            "predicted": [
                (p["canonical_type"], p["text"], p["score"]) for p in predicted_items
            ],
            "tp": sorted(list(tp_set)),
            "fp": [p for p in predicted_items if (p["canonical_type"], p["text"]) in fp_set],
            "fn": sorted(list(fn_set)),
            "latency_ms": round(elapsed * 1000, 2),
        }
        sample_results.append(sample_detail)

        if fp > 0 or fn > 0:
            mismatches.append(sample_detail)

    overall_precision, overall_recall, overall_f1 = calculate_prf(
        overall_tp, overall_fp, overall_fn
    )
    avg_latency_ms = (
        (total_inference_time_s / total_samples * 1000) if total_samples > 0 else 0.0
    )

    per_type_metrics: Dict[str, Dict[str, Any]] = {}
    for etype in sorted(per_type.keys()):
        counts = per_type[etype]
        p, r, f = calculate_prf(counts["tp"], counts["fp"], counts["fn"])
        per_type_metrics[etype] = {
            "expected": counts["expected"],
            "predicted": counts["predicted"],
            "tp": counts["tp"],
            "fp": counts["fp"],
            "fn": counts["fn"],
            "precision": p,
            "recall": r,
            "f1": f,
        }

    return {
        "model_name": DEFAULT_MODEL_NAME,
        "device": device,
        "threshold": threshold,
        "total_samples": total_samples,
        "total_expected_entities": total_expected_entities,
        "total_predicted_entities": total_predicted_entities,
        "tp": overall_tp,
        "fp": overall_fp,
        "fn": overall_fn,
        "precision": overall_precision,
        "recall": overall_recall,
        "f1": overall_f1,
        "total_inference_time_s": round(total_inference_time_s, 4),
        "avg_latency_ms": round(avg_latency_ms, 2),
        "per_type": per_type_metrics,
        "mismatches": mismatches,
        "samples": sample_results,
    }


def format_report(results: Dict[str, Any]) -> str:
    """Format evaluation results into a clean, comprehensive text report."""
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("GLiNER BENCHMARK EVALUATION REPORT")
    lines.append("=" * 80)
    lines.append(f"Model       : {results['model_name']}")
    lines.append(f"Device      : {results['device']}")
    threshold_str = str(results['threshold']) if results['threshold'] is not None else "Default (0.5)"
    lines.append(f"Threshold   : {threshold_str}")
    lines.append(f"Samples     : {results['total_samples']}")
    lines.append(f"Expected    : {results['total_expected_entities']}")
    lines.append(f"Predicted   : {results['total_predicted_entities']}")
    lines.append("-" * 80)
    lines.append("OVERALL METRICS")
    lines.append("-" * 80)
    lines.append(f"True Positives (TP)  : {results['tp']}")
    lines.append(f"False Positives (FP) : {results['fp']}")
    lines.append(f"False Negatives (FN) : {results['fn']}")
    lines.append(f"Precision            : {results['precision']:.4f} ({results['precision']*100:.1f}%)")
    lines.append(f"Recall               : {results['recall']:.4f} ({results['recall']*100:.1f}%)")
    lines.append(f"F1-Score             : {results['f1']:.4f} ({results['f1']*100:.1f}%)")
    lines.append(f"Total Inference Time : {results['total_inference_time_s']:.3f} s")
    lines.append(f"Avg Latency / Sample : {results['avg_latency_ms']:.2f} ms")
    lines.append("-" * 80)
    lines.append("PER-ENTITY-TYPE BREAKDOWN")
    lines.append("-" * 80)
    header = f"{'Entity Type':<12} {'Exp':<5} {'Pred':<5} {'TP':<5} {'FP':<5} {'FN':<5} {'Precision':<10} {'Recall':<10} {'F1-Score':<10}"
    lines.append(header)
    lines.append("-" * len(header))
    for etype, m in sorted(results["per_type"].items()):
        lines.append(
            f"{etype:<12} {m['expected']:<5} {m['predicted']:<5} {m['tp']:<5} {m['fp']:<5} {m['fn']:<5} "
            f"{m['precision']:<10.4f} {m['recall']:<10.4f} {m['f1']:<10.4f}"
        )
    lines.append("-" * 80)
    lines.append(f"MISMATCHES ({len(results['mismatches'])} samples with FP or FN)")
    lines.append("-" * 80)

    if not results["mismatches"]:
        lines.append("None! Perfect prediction across all samples.")
    else:
        for idx, m in enumerate(results["mismatches"], 1):
            lines.append(f"[{idx}] ID: {m['id']} (Category: {m['category']})")
            lines.append(f"    Text    : \"{m['text']}\"")
            if m["expected"]:
                lines.append(f"    Expected: {m['expected']}")
            else:
                lines.append("    Expected: [] (Negative case)")

            if m["predicted"]:
                pred_strs = [f"({p[0]}, '{p[1]}', conf={p[2]})" for p in m["predicted"]]
                lines.append(f"    Predicted: {', '.join(pred_strs)}")
            else:
                lines.append("    Predicted: []")

            if m["fn"]:
                lines.append(f"    [FN] False Negatives: {m['fn']}")
            if m["fp"]:
                fp_strs = [f"({p['canonical_type']}, '{p['text']}', conf={p['score']})" for p in m["fp"]]
                lines.append(f"    [FP] False Positives: {fp_strs}")
            lines.append("")

    lines.append("=" * 80)
    return "\n".join(lines)


def main():
    """Execute GLiNER benchmark evaluation and print report."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print("Loading benchmark and urchade/gliner_multi_pii-v1 model...")
    results = evaluate()
    report = format_report(results)
    print(report)


if __name__ == "__main__":
    main()
