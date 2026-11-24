"""
GLiNER Threshold Sweep Experiment.

Evaluates GLiNER models at multiple confidence thresholds (0.30 - 0.70)
using the 30-sample benchmark and existing model adapters.
"""

import csv
import gc
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import torch

# Ensure backend root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.gliner_evaluator import (
    DEFAULT_ADAPTER,
    GRETEL_ADAPTER,
    LABEL_MAPPING,
    ModelLabelAdapter,
    calculate_prf,
    evaluate,
    get_adapter,
    load_benchmark,
    load_gliner_model,
)

CANONICAL_BENCHMARK_TYPES: List[str] = [
    "NAME", "EMAIL", "PHONE", "PAN", "CARD", "ACCOUNT", "IP", "URL", "API_KEY", "JWT"
]

DEFAULT_THRESHOLDS: List[float] = [0.30, 0.40, 0.50, 0.60, 0.70]

SWEEP_MODELS: List[Dict[str, str]] = [
    {
        "model_name": "urchade/gliner_multi_pii-v1",
        "adapter_name": "default",
    },
    {
        "model_name": "knowledgator/gliner-pii-small-v1.0",
        "adapter_name": "default",
    },
    {
        "model_name": "gretelai/gretel-gliner-bi-small-v1.0",
        "adapter_name": "gretel",
    },
]

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"


def measure_inference_latency(
    model: Any,
    samples: List[Dict[str, Any]],
    prompt_labels: List[str],
    device: str,
    threshold: float = 0.5,
    warmup_passes: int = 1,
    timed_passes: int = 3,
) -> Dict[str, Any]:
    """Measure inference latency across benchmark samples with warm-up and CUDA synchronization.

    Returns:
        Dictionary with warmup time, measured time, number of passes, and average per-sample latency.
    """
    if not samples:
        return {
            "warmup_time_s": 0.0,
            "measured_time_s": 0.0,
            "timed_passes": timed_passes,
            "avg_latency_ms": 0.0,
        }

    is_cuda = device == "cuda" and torch.cuda.is_available()

    # 1. Warm-up pass
    if is_cuda:
        torch.cuda.synchronize()
    t_warmup_start = time.perf_counter()
    for _ in range(warmup_passes):
        for s in samples:
            _ = model.predict_entities(s["text"], prompt_labels, threshold=threshold)
    if is_cuda:
        torch.cuda.synchronize()
    warmup_time_s = time.perf_counter() - t_warmup_start

    # 2. Timed measurement passes
    if is_cuda:
        torch.cuda.synchronize()
    t_timed_start = time.perf_counter()
    for _ in range(timed_passes):
        for s in samples:
            _ = model.predict_entities(s["text"], prompt_labels, threshold=threshold)
    if is_cuda:
        torch.cuda.synchronize()
    measured_time_s = time.perf_counter() - t_timed_start

    total_inferences = len(samples) * timed_passes
    avg_latency_ms = (measured_time_s / total_inferences * 1000) if total_inferences > 0 else 0.0

    return {
        "warmup_time_s": round(warmup_time_s, 4),
        "measured_time_s": round(measured_time_s, 4),
        "timed_passes": timed_passes,
        "avg_latency_ms": round(avg_latency_ms, 2),
    }


def run_threshold_sweep(
    models_config: Optional[List[Dict[str, str]]] = None,
    thresholds: Optional[List[float]] = None,
    benchmark: Optional[List[Dict[str, Any]]] = None,
    model_loader: Optional[Callable[[str, Optional[str]], Tuple[Any, str]]] = None,
    results_dir: Optional[Path] = None,
    save_files: bool = True,
    measure_latency: bool = True,
) -> Dict[str, Any]:
    """Execute the threshold sweep sequentially across models and thresholds.

    Loads each model once, measures latency and evaluates all thresholds.
    """
    if models_config is None:
        models_config = SWEEP_MODELS
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS
    if benchmark is None:
        benchmark = load_benchmark()
    if model_loader is None:
        model_loader = load_gliner_model
    if results_dir is None:
        results_dir = DEFAULT_RESULTS_DIR

    records: List[Dict[str, Any]] = []
    latency_reports: Dict[str, Any] = {}

    for config in models_config:
        model_name = config["model_name"]
        adapter_name = config.get("adapter_name")
        adapter = get_adapter(adapter_name if adapter_name else model_name)

        print(f"\n[Threshold Sweep] Loading model: {model_name} (adapter: {adapter.name})...")
        t_load_start = time.perf_counter()
        model, device = model_loader(model_name)
        load_time_s = round(time.perf_counter() - t_load_start, 2)
        print(f"Loaded on {device} in {load_time_s}s.")

        # Latency measurement
        if measure_latency:
            print(f"Measuring latency (1 warm-up pass, 3 timed passes over {len(benchmark)} samples)...")
            lat_stats = measure_inference_latency(
                model=model,
                samples=benchmark,
                prompt_labels=adapter.prompt_labels,
                device=device,
                threshold=0.5,
                warmup_passes=1,
                timed_passes=3,
            )
            latency_reports[model_name] = {
                "load_time_s": load_time_s,
                **lat_stats,
            }
            avg_latency_ms = lat_stats["avg_latency_ms"]
            print(f"Latency: {avg_latency_ms} ms/sample (warmup: {lat_stats['warmup_time_s']}s, measured: {lat_stats['measured_time_s']}s)")
        else:
            avg_latency_ms = 0.0
            latency_reports[model_name] = {
                "load_time_s": load_time_s,
                "avg_latency_ms": 0.0,
            }

        # Evaluate all thresholds on the loaded model
        for thresh in thresholds:
            print(f"  Evaluating threshold {thresh:.2f}...")
            eval_res = evaluate(
                benchmark=benchmark,
                model=model,
                model_name=model_name,
                adapter=adapter,
                device=device,
                threshold=thresh,
            )

            record = {
                "model_name": model_name,
                "adapter": adapter.name,
                "threshold": round(thresh, 2),
                "tp": eval_res["tp"],
                "fp": eval_res["fp"],
                "fn": eval_res["fn"],
                "precision": eval_res["precision"],
                "recall": eval_res["recall"],
                "f1": eval_res["f1"],
                "expected_entities": eval_res["total_expected_entities"],
                "predicted_entities": eval_res["total_predicted_entities"],
                "latency_ms": avg_latency_ms,
                "per_type": eval_res["per_type"],
            }
            records.append(record)

        # Free GPU memory before next model
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    summary_data = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_benchmark_samples": len(benchmark),
            "thresholds_evaluated": thresholds,
            "models_evaluated": [c["model_name"] for c in models_config],
        },
        "records": records,
        "latency_summary": latency_reports,
    }

    if save_files:
        save_results(records, summary_data, results_dir)

    return summary_data


def save_results(
    records: List[Dict[str, Any]],
    detailed_data: Dict[str, Any],
    results_dir: Path,
) -> Tuple[Path, Path]:
    """Write summary CSV and detailed JSON files."""
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / "threshold_sweep_summary.csv"
    json_path = results_dir / "threshold_sweep_detailed.json"

    fieldnames = [
        "model_name",
        "adapter",
        "threshold",
        "tp",
        "fp",
        "fn",
        "precision",
        "recall",
        "f1",
        "expected_entities",
        "predicted_entities",
        "latency_ms",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            row = {k: r[k] for k in fieldnames}
            writer.writerow(row)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(detailed_data, f, indent=2)

    print(f"\n[Results Saved]")
    print(f"Summary CSV : {csv_path}")
    print(f"Detailed JSON: {json_path}")
    return csv_path, json_path


def format_comparison_table(records: List[Dict[str, Any]]) -> str:
    """Format evaluation records into a readable comparison table."""
    lines: List[str] = []
    lines.append("=" * 110)
    lines.append(f"{'Model':<40} {'Adapter':<9} {'Thresh':<7} {'Exp':<5} {'Pred':<5} {'TP':<4} {'FP':<4} {'FN':<4} {'Prec':<7} {'Recall':<7} {'F1':<7} {'Lat (ms)':<8}")
    lines.append("-" * 110)

    current_model = None
    for r in records:
        if current_model is not None and r["model_name"] != current_model:
            lines.append("-" * 110)
        current_model = r["model_name"]

        lines.append(
            f"{r['model_name']:<40} {r['adapter']:<9} {r['threshold']:<7.2f} {r['expected_entities']:<5} {r['predicted_entities']:<5} "
            f"{r['tp']:<4} {r['fp']:<4} {r['fn']:<4} {r['precision']:<7.4f} {r['recall']:<7.4f} {r['f1']:<7.4f} {r['latency_ms']:<8.2f}"
        )
    lines.append("=" * 110)
    return "\n".join(lines)


def main():
    """Execute the full threshold sweep experiment and print the comparison table."""
    results = run_threshold_sweep()
    table = format_comparison_table(results["records"])
    print("\n" + table)


if __name__ == "__main__":
    main()
