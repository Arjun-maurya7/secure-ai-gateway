import json
import sys
import time
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from detection.engine import DetectionEngine


def load_benchmark(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Return (precision, recall, F1) for the given counts."""
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)


def evaluate(benchmark: list[dict]) -> dict:
    """Run the benchmark and return a comprehensive metrics dictionary.

    Returned keys:
        total_samples, total_expected, total_detected,
        true_positive, false_positive, false_negative,
        precision, recall, f1,
        total_time_s, avg_latency_ms,
        per_type: dict[str, dict]   — per-entity-type TP/FP/FN/precision/recall/f1
        mismatches: list[dict]      — details of every sample that had errors
    """
    engine = DetectionEngine()

    overall_tp = overall_fp = overall_fn = 0
    total_expected = 0
    total_detected_count = 0
    per_type: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    mismatches: list[dict] = []
    total_time = 0.0

    for sample in benchmark:
        text = sample["text"]
        expected_entities = sample.get("entities", [])

        t0 = time.perf_counter()
        detected_entities = engine.detect(text)
        elapsed = time.perf_counter() - t0
        total_time += elapsed

        expected = {(e["type"], e["value"]) for e in expected_entities}
        detected = {(e.type, e.value) for e in detected_entities}

        missing = expected - detected
        unexpected = detected - expected

        total_expected += len(expected)
        total_detected_count += len(detected)

        tp = len(expected & detected)
        fp = len(unexpected)
        fn = len(missing)

        overall_tp += tp
        overall_fp += fp
        overall_fn += fn

        # Per-type accounting
        for etype, _val in (expected & detected):
            per_type[etype]["tp"] += 1
        for etype, _val in unexpected:
            per_type[etype]["fp"] += 1
        for etype, _val in missing:
            per_type[etype]["fn"] += 1

        if missing or unexpected:
            mismatches.append({
                "text": text,
                "missing": sorted(missing),
                "unexpected": sorted(unexpected),
            })

    precision, recall, f1 = _prf(overall_tp, overall_fp, overall_fn)
    avg_latency_ms = (total_time / len(benchmark) * 1000) if benchmark else 0.0

    per_type_metrics: dict[str, dict] = {}
    for etype, counts in sorted(per_type.items()):
        p, r, f = _prf(counts["tp"], counts["fp"], counts["fn"])
        per_type_metrics[etype] = {
            "tp": counts["tp"],
            "fp": counts["fp"],
            "fn": counts["fn"],
            "precision": p,
            "recall": r,
            "f1": f,
        }

    return {
        "total_samples": len(benchmark),
        "total_expected": total_expected,
        "total_detected": total_detected_count,
        "true_positive": overall_tp,
        "false_positive": overall_fp,
        "false_negative": overall_fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "total_time_s": round(total_time, 3),
        "avg_latency_ms": round(avg_latency_ms, 2),
        "per_type": per_type_metrics,
        "mismatches": mismatches,
    }


def print_report(results: dict) -> None:
    sep = "-" * 50

    print(sep)
    print("Banking PII Detector — Evaluation Report")
    print(sep)
    print(f"Total samples      : {results['total_samples']}")
    print(f"Total expected     : {results['total_expected']}")
    print(f"Total detected     : {results['total_detected']}")
    print(sep)
    print(f"True Positives     : {results['true_positive']}")
    print(f"False Positives    : {results['false_positive']}")
    print(f"False Negatives    : {results['false_negative']}")
    print(sep)
    print(f"Precision          : {results['precision']:.4f}")
    print(f"Recall             : {results['recall']:.4f}")
    print(f"F1 Score           : {results['f1']:.4f}")
    print(sep)
    print(f"Total eval time    : {results['total_time_s']:.3f}s")
    print(f"Avg latency/sample : {results['avg_latency_ms']:.2f}ms")

    print()
    print("Per-Entity-Type Metrics")
    print(sep)
    for etype, m in results["per_type"].items():
        print(f"  {etype:<12}  TP={m['tp']:>3}  FP={m['fp']:>3}  FN={m['fn']:>3}"
              f"  P={m['precision']:.3f}  R={m['recall']:.3f}  F1={m['f1']:.3f}")

    if results["mismatches"]:
        print()
        print("Mismatches")
        print(sep)
        for mm in results["mismatches"]:
            print(f"  Text     : {mm['text'][:80]}")
            if mm["missing"]:
                print(f"  Missing  : {mm['missing']}")
            if mm["unexpected"]:
                print(f"  Unexpected: {mm['unexpected']}")
            print()
    else:
        print()
        print("No mismatches — all samples matched perfectly.")


if __name__ == "__main__":
    benchmark_path = Path(__file__).with_name("benchmark.json")
    benchmark = load_benchmark(benchmark_path)
    results = evaluate(benchmark)
    print_report(results)