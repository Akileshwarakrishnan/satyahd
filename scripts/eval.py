"""Eval script for Satyahd guardrail pipeline.

Runs 30 synthetic drafts through the extraction + verification pipeline,
computes precision / recall for block/allow/review labels, and saves results
to eval_results.json.

Usage:
    python scripts/eval.py [--output eval_results.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Ensure project root is on PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("ALLOW_MOCK", "true")

from app.extract import extract_promises
from app.rules import load_rules
from app.verify import Verdict, collect_facts, verify

EVAL_DRAFTS = PROJECT_ROOT / "data" / "eval_drafts.json"


def classify(draft: str, customer: str, interaction_id: str) -> str:
    """Run a draft through extract → verify and return 'allow', 'block', or 'review'."""
    promises, status = extract_promises(draft=draft, customer_message=customer, interaction_id=interaction_id)
    if status != "ok":
        return "review"

    rules = load_rules()
    facts = collect_facts(promises=promises, interaction_id=interaction_id)
    res = verify(promises, rules, facts)

    verdict_map = {
        Verdict.ALLOW: "allow",
        Verdict.BLOCK: "block",
        Verdict.REVIEW: "review",
    }
    return verdict_map.get(res.message_verdict, "review")


def compute_metrics(
    cases: list[dict],
    predictions: list[str],
) -> dict:
    """Compute per-class precision and recall."""
    labels = [c["label"] for c in cases]
    classes = ["allow", "block", "review"]
    metrics: dict = {}
    for cls in classes:
        tp = sum(1 for l, p in zip(labels, predictions) if l == cls and p == cls)
        fp = sum(1 for l, p in zip(labels, predictions) if l != cls and p == cls)
        fn = sum(1 for l, p in zip(labels, predictions) if l == cls and p != cls)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        metrics[cls] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }
    overall_correct = sum(1 for l, p in zip(labels, predictions) if l == p)
    metrics["overall_accuracy"] = round(overall_correct / len(labels), 4) if labels else 0.0
    return metrics


def main(output_path: Path) -> None:
    if not EVAL_DRAFTS.exists():
        print(f"[ERROR] eval_drafts.json not found at {EVAL_DRAFTS}")
        sys.exit(1)

    cases: list[dict] = json.loads(EVAL_DRAFTS.read_text(encoding="utf-8"))
    print(f"Loaded {len(cases)} eval cases.")

    results = []
    predictions = []
    t0 = time.perf_counter()

    for i, case in enumerate(cases):
        iid = f"eval_{case['id']}"
        pred = classify(
            draft=case["draft"],
            customer=case["customer"],
            interaction_id=iid,
        )
        correct = pred == case["label"]
        predictions.append(pred)
        results.append({
            "id": case["id"],
            "label": case["label"],
            "prediction": pred,
            "correct": correct,
            "customer": case["customer"][:60],
            "draft_snippet": case["draft"][:80],
        })
        status_icon = "✓" if correct else "✗"
        print(f"  [{i+1:02d}] {status_icon} {case['id']} | label={case['label']:8s} pred={pred:8s} — {case['draft'][:55]}…")

    elapsed = time.perf_counter() - t0
    metrics = compute_metrics(cases, predictions)
    accuracy = metrics["overall_accuracy"]

    print(f"\n{'─'*60}")
    print(f"Accuracy:  {accuracy*100:.1f}%  ({sum(1 for r in results if r['correct'])}/{len(results)} correct)")
    for cls in ["allow", "block", "review"]:
        m = metrics[cls]
        print(f"  {cls:8s} → P={m['precision']:.2f}  R={m['recall']:.2f}  F1={m['f1']:.2f}")
    print(f"Elapsed:   {elapsed:.2f}s")
    print(f"{'─'*60}\n")

    output = {
        "total": len(cases),
        "correct": sum(1 for r in results if r["correct"]),
        "accuracy": accuracy,
        "metrics_per_class": metrics,
        "elapsed_seconds": round(elapsed, 3),
        "results": results,
    }
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Results saved to: {output_path}")

    if accuracy < 0.70:
        print("[WARN] Accuracy below 70% threshold. Review guardrail logic.")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Satyahd Eval Script")
    parser.add_argument("--output", default="eval_results.json", help="Output JSON file path")
    args = parser.parse_args()
    main(Path(args.output))
