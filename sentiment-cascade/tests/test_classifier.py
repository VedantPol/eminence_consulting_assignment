"""Gate logic + label normalization — no model download required."""
from app.classifier import SentimentClassifier
from app.config import Settings
from app.pipeline import should_escalate
from app.schemas import ClassifierResult, Polarity


def _clf(conf, margin, label="positive"):
    return ClassifierResult(
        label=Polarity(label), confidence=conf,
        distribution={"positive": conf, "neutral": 0, "negative": 0},
        top2_margin=margin,
    )


def test_high_confidence_does_not_escalate():
    s = Settings(conf_threshold=0.85, margin_threshold=0.15)
    esc, reason = should_escalate(_clf(0.97, 0.9), "great app", False, s)
    assert esc is False and reason == "high_confidence"


def test_low_confidence_escalates():
    s = Settings(conf_threshold=0.85, margin_threshold=0.15)
    esc, reason = should_escalate(_clf(0.70, 0.5), "meh", False, s)
    assert esc is True and reason.startswith("low_confidence")


def test_narrow_margin_escalates_even_if_confident_enough():
    s = Settings(conf_threshold=0.60, margin_threshold=0.15)
    esc, reason = should_escalate(_clf(0.62, 0.05), "mixed feelings", False, s)
    assert esc is True and reason.startswith("narrow_margin")


def test_require_aspects_always_escalates():
    s = Settings()
    esc, reason = should_escalate(_clf(0.99, 0.99), "x", True, s)
    assert esc is True and reason == "require_aspects"


def test_length_gate_is_off_by_default():
    s = Settings()  # escalate_on_length=0
    esc, _ = should_escalate(_clf(0.99, 0.99), "x" * 5000, False, s)
    assert esc is False


def test_threshold_boundary_is_strict_less_than():
    s = Settings(conf_threshold=0.85, margin_threshold=0.0)
    # confidence exactly at threshold should NOT escalate
    esc, _ = should_escalate(_clf(0.85, 0.9), "x", False, s)
    assert esc is False


def test_label_normalization_maps_finbert_and_roberta():
    finbert = [{"label": "positive", "score": 0.8},
               {"label": "negative", "score": 0.05},
               {"label": "neutral", "score": 0.15}]
    roberta = [{"label": "LABEL_2", "score": 0.7},
               {"label": "LABEL_1", "score": 0.2},
               {"label": "LABEL_0", "score": 0.1}]
    for scores in (finbert, roberta):
        dist = SentimentClassifier._normalize(scores)
        assert max(dist, key=dist.get) == "positive"
        assert abs(sum(dist.values()) - 1.0) < 1e-6
