"""Cascade routing with fake classifier/backend — exercises gate + fallback logic
without loading any model."""
import pytest

from app.config import Settings
from app.pipeline import CascadePipeline
from app.schemas import AnalyzeResponse, ClassifierResult, Polarity, Sentiment


class FakeClassifier:
    def __init__(self, conf, margin, label="positive"):
        self._r = ClassifierResult(
            label=Polarity(label), confidence=conf,
            distribution={"positive": conf, "neutral": 0, "negative": 0},
            top2_margin=margin,
        )

    def predict(self, text):
        return self._r

    def predict_batch(self, texts):
        return [self._r for _ in texts]


class FakeBackend:
    source = "llm"

    def __init__(self, raise_exc=False):
        self.raise_exc = raise_exc
        self.calls = 0

    async def analyze(self, masked_text, require_aspects):
        self.calls += 1
        if self.raise_exc:
            raise RuntimeError("boom")
        return AnalyzeResponse(
            overall_sentiment=Sentiment.mixed, confidence=0.9, aspects=[],
            source="llm", language="en", rationale="fake")


def _pipeline(clf, backend, **overrides):
    p = object.__new__(CascadePipeline)  # bypass model-loading __init__
    p.settings = Settings(**overrides)
    p.classifier = clf
    p.backend = backend
    p.judge = None
    return p


async def test_high_confidence_resolves_on_classifier():
    p = _pipeline(FakeClassifier(0.97, 0.9), FakeBackend())
    r = await p.analyze_one("the app is great")
    assert r.source == "classifier"
    assert r.overall_sentiment == Sentiment.positive
    assert p.backend.calls == 0  # LLM never touched


async def test_low_confidence_escalates_to_llm():
    p = _pipeline(FakeClassifier(0.6, 0.4), FakeBackend())
    r = await p.analyze_one("meh, could be better")
    assert r.source == "llm"
    assert p.backend.calls == 1


async def test_llm_failure_falls_back_to_classifier():
    p = _pipeline(FakeClassifier(0.6, 0.4, label="negative"), FakeBackend(raise_exc=True))
    r = await p.analyze_one("ambiguous text")
    assert r.source == "classifier_fallback"
    assert r.overall_sentiment == Sentiment.negative  # falls back to classifier verdict


async def test_batch_reports_escalation_rate():
    # classifier is low-confidence -> every item escalates -> rate 1.0
    p = _pipeline(FakeClassifier(0.5, 0.1), FakeBackend())
    results, rate = await p.analyze_batch(["a", "b", "c"])
    assert len(results) == 3
    assert rate == 1.0
    assert all(r.source == "llm" for r in results)
