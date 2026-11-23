import json
import sys
from collections import Counter
from pathlib import Path

bench_path = Path(__file__).parent / "gliner_benchmark.json"
with open(bench_path, encoding="utf-8") as f:
    data = json.load(f)

errors = []
ids = set()
for i, sample in enumerate(data):
    sid = sample.get("id", f"[missing id at index {i}]")
    if sid in ids:
        errors.append(f"{sid}: duplicate id")
    ids.add(sid)
    if "text" not in sample:
        errors.append(f"{sid}: missing 'text' field")
    if "entities" not in sample:
        errors.append(f"{sid}: missing 'entities' field")
    for ent in sample.get("entities", []):
        if "text" not in ent:
            errors.append(f"{sid}: entity missing 'text' field")
        if "label" not in ent:
            errors.append(f"{sid}: entity missing 'label' field")
        ent_text = ent.get("text", "")
        sample_text = sample.get("text", "")
        if ent_text not in sample_text:
            errors.append(f"{sid}: entity text not found in sample: {repr(ent_text)}")

cats = Counter(s.get("category", "?") for s in data)
labels_used = Counter(e["label"] for s in data for e in s.get("entities", []))
neg = sum(1 for s in data if s.get("entities") == [])

print(f"Total test cases  : {len(data)}")
print(f"Negative cases    : {neg}")
print(f"Categories        : {dict(cats)}")
print(f"Labels used:")
for label, count in sorted(labels_used.items()):
    print(f"  {label:<24} {count}")
print(f"Validation errors : {len(errors)}")
if errors:
    for e in errors:
        print(f"  ERROR: {e}")
    sys.exit(1)
else:
    print("JSON is valid — all entity texts found in their parent samples.")
