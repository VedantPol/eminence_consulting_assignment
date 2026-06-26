"""
Benchmark harness — compare classifier-only vs cascade (vs LLM-only if a key is
set) on a small labelled set. Reports accuracy, macro-F1, escalation rate, and
mean latency so you can tune CONF_THRESHOLD against the cost/accuracy tradeoff.

Run:  python -m tests.eval            (from the project root)
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd

from app.classifier import get_classifier
from app.config import get_settings
from app.llm import LocalEscalationBackend, get_escalation_backend
from app.pipeline import CascadePipeline
from app.schemas import Sentiment

LABELS = ["positive", "negative", "neutral", "mixed"]
DATA = Path(__file__).parent / "data" / "eval.csv"


def macro_f1(y_true: list[str], y_pred: list[str]) -> float:
    f1s = []
    for lab in LABELS:
        tp = sum(t == lab and p == lab for t, p in zip(y_true, y_pred))
        fp = sum(t != lab and p == lab for t, p in zip(y_true, y_pred))
        fn = sum(t == lab and p != lab for t, p in zip(y_true, y_pred))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(f1s) / len(f1s)


def accuracy(y_true, y_pred) -> float:
    return sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true)


async def main() -> None:
    df = pd.read_csv(DATA)
    texts, labels = df["text"].tolist(), df["label"].tolist()
    s = get_settings()
    print(f"Eval set: {len(texts)} examples | classifier={s.classifier_model} "
          f"| llm_backend={'claude' if s.claude_enabled else 'local'}\n")

    # ---- classifier-only -----------------------------------------------------
    clf = get_classifier()
    t0 = time.perf_counter()
    clf_pred = [r.label.value for r in clf.predict_batch(texts)]
    clf_ms = (time.perf_counter() - t0) * 1000 / len(texts)

    # ---- cascade -------------------------------------------------------------
    pipe = CascadePipeline(s)
    t0 = time.perf_counter()
    cascade_results, esc_rate = await pipe.analyze_batch(texts)
    cascade_ms = (time.perf_counter() - t0) * 1000 / len(texts)
    cascade_pred = [r.overall_sentiment.value for r in cascade_results]
    sources = defaultdict(int)
    for r in cascade_results:
        sources[r.source] += 1

    # ---- report --------------------------------------------------------------
    rows = [
        ("classifier-only", accuracy(labels, clf_pred), macro_f1(labels, clf_pred),
         0.0, clf_ms),
        ("cascade", accuracy(labels, cascade_pred), macro_f1(labels, cascade_pred),
         esc_rate, cascade_ms),
    ]
    print(f"{'approach':<18}{'accuracy':>10}{'macro_f1':>10}{'escalation':>12}{'ms/item':>10}")
    print("-" * 60)
    for name, acc, f1, esc, ms in rows:
        print(f"{name:<18}{acc:>10.3f}{f1:>10.3f}{esc:>12.1%}{ms:>10.1f}")
    print(f"\ncascade routing: {dict(sources)}")
    if not s.claude_enabled:
        print("(LLM-only row omitted — no ANTHROPIC_API_KEY; escalations used the "
              "local backend.)")


if __name__ == "__main__":
    asyncio.run(main())
