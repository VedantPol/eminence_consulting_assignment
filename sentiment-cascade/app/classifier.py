"""
Fast local sentiment classifier (HuggingFace transformers).

Loaded once at startup (singleton), runs on GPU if available else CPU, supports
batched inference. Returns the label, max-softmax confidence, the full
distribution, and the top-2 margin (used by the gate to spot mixed/uncertain text).
"""
from __future__ import annotations

import functools

from .config import get_settings
from .schemas import ClassifierResult, Polarity

# Map the various label vocabularies models use onto our 3 polarities.
_LABEL_MAP = {
    "positive": "positive", "pos": "positive", "label_2": "positive",
    "neutral": "neutral", "neu": "neutral", "label_1": "neutral",
    "negative": "negative", "neg": "negative", "label_0": "negative",
}


class SentimentClassifier:
    def __init__(self, model_name: str, max_length: int = 256):
        from transformers import pipeline
        import torch

        device = 0 if torch.cuda.is_available() else -1
        self.model_name = model_name
        self.device = "cuda" if device == 0 else "cpu"
        self._pipe = pipeline(
            "text-classification",
            model=model_name,
            device=device,
            top_k=None,            # return scores for all classes
            truncation=True,
            max_length=max_length,
        )

    @staticmethod
    def _normalize(scores: list[dict]) -> dict[str, float]:
        dist = {"positive": 0.0, "neutral": 0.0, "negative": 0.0}
        for s in scores:
            key = _LABEL_MAP.get(s["label"].lower())
            if key:
                dist[key] = float(s["score"])
        return dist

    def _to_result(self, scores: list[dict]) -> ClassifierResult:
        dist = self._normalize(scores)
        ranked = sorted(dist.values(), reverse=True)
        label = max(dist, key=dist.get)
        margin = round(ranked[0] - ranked[1], 4) if len(ranked) > 1 else ranked[0]
        return ClassifierResult(
            label=Polarity(label),
            confidence=round(ranked[0], 4),
            distribution={k: round(v, 4) for k, v in dist.items()},
            top2_margin=margin,
        )

    def predict(self, text: str) -> ClassifierResult:
        return self.predict_batch([text])[0]

    def predict_batch(self, texts: list[str]) -> list[ClassifierResult]:
        # text-classification with top_k=None returns list[list[dict]] for a list input
        out = self._pipe(texts, batch_size=min(32, len(texts)))
        if texts and isinstance(out[0], dict):  # single-item edge case
            out = [out]
        return [self._to_result(scores) for scores in out]


@functools.lru_cache(maxsize=1)
def get_classifier() -> SentimentClassifier:
    s = get_settings()
    return SentimentClassifier(s.classifier_model, s.classifier_max_length)
