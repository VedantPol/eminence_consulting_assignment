"""
Cascade orchestration: PII mask -> fast classifier -> confidence gate ->
(escalate to LLM) -> (optional judge), with a classifier fallback on LLM failure.

Routing target: the classifier resolves the easy majority; only low-confidence,
mixed, or aspect-requested inputs reach the LLM.
"""
from __future__ import annotations

import asyncio
import logging
import time

from . import pii
from .classifier import get_classifier
from .config import Settings, get_settings
from .llm import LocalEscalationBackend, _detect_lang, get_escalation_backend
from .schemas import AnalyzeResponse, ClassifierResult, Sentiment

log = logging.getLogger("cascade")


def should_escalate(
    clf: ClassifierResult, masked_text: str, require_aspects: bool, settings: Settings
) -> tuple[bool, str]:
    """Return (escalate?, reason). Thresholds are all configurable."""
    if require_aspects:
        return True, "require_aspects"
    if clf.confidence < settings.conf_threshold:
        return True, f"low_confidence({clf.confidence:.2f}<{settings.conf_threshold})"
    if clf.top2_margin < settings.margin_threshold:
        return True, f"narrow_margin({clf.top2_margin:.2f}<{settings.margin_threshold})"
    if settings.escalate_on_length and len(masked_text) > settings.escalate_on_length:
        return True, f"long_text(>{settings.escalate_on_length})"
    return False, "high_confidence"


class CascadePipeline:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.classifier = get_classifier()
        self.backend = get_escalation_backend()
        self.judge = None
        if self.settings.enable_judge and not isinstance(self.backend, LocalEscalationBackend):
            from .judge import Judge

            self.judge = Judge(self.settings)

    # -- public ---------------------------------------------------------------
    async def analyze_one(self, text: str, require_aspects: bool = False) -> AnalyzeResponse:
        masked, _ = pii.mask(text)
        clf = self.classifier.predict(masked)
        return await self._route(masked, clf, require_aspects)

    async def analyze_batch(
        self, texts: list[str], require_aspects: bool = False
    ) -> tuple[list[AnalyzeResponse], float]:
        masked = [pii.mask(t)[0] for t in texts]
        clf_results = self.classifier.predict_batch(masked)  # one forward pass
        sem = asyncio.Semaphore(self.settings.max_llm_concurrency)

        async def handle(i: int) -> AnalyzeResponse:
            esc, reason = should_escalate(clf_results[i], masked[i], require_aspects, self.settings)
            if not esc:
                return self._classifier_response(masked[i], clf_results[i], "classifier")
            async with sem:  # bound concurrent LLM calls
                return await self._escalate(masked[i], clf_results[i], require_aspects, reason)

        results = await asyncio.gather(*[handle(i) for i in range(len(texts))])
        escalated = sum(1 for r in results if r.source != "classifier")
        return list(results), round(escalated / len(results), 4)

    # -- internals ------------------------------------------------------------
    async def _route(self, masked: str, clf: ClassifierResult, require_aspects: bool):
        esc, reason = should_escalate(clf, masked, require_aspects, self.settings)
        if not esc:
            log.info("decision=classifier reason=%s conf=%.2f text=%r",
                     reason, clf.confidence, _short(masked))
            return self._classifier_response(masked, clf, "classifier")
        return await self._escalate(masked, clf, require_aspects, reason)

    async def _escalate(self, masked: str, clf: ClassifierResult, require_aspects: bool, reason: str):
        t0 = time.perf_counter()
        try:
            resp = await self.backend.analyze(masked, require_aspects)
        except Exception as e:
            log.warning("decision=escalate->fallback reason=%s error=%s text=%r",
                        reason, e, _short(masked))
            return self._classifier_response(masked, clf, "classifier_fallback")

        dt = (time.perf_counter() - t0) * 1000
        log.info("decision=escalate reason=%s source=%s latency_ms=%.0f text=%r",
                 reason, resp.source, dt, _short(masked))

        if self.judge is not None and resp.source == "llm" \
                and clf.label.value != resp.overall_sentiment.value:
            try:
                resp = await self.judge.adjudicate(masked, clf.label.value, resp)
                log.info("decision=judge final=%s", resp.overall_sentiment.value)
            except Exception as e:
                log.warning("judge_failed error=%s (keeping llm verdict)", e)
        return resp

    @staticmethod
    def _classifier_response(masked: str, clf: ClassifierResult, source) -> AnalyzeResponse:
        return AnalyzeResponse(
            overall_sentiment=Sentiment(clf.label.value),
            confidence=clf.confidence,
            aspects=[],
            source=source,
            language=_detect_lang(masked),
            rationale=None,
        )


def _short(text: str, n: int = 80) -> str:
    """Masked text is already PII-free; truncate for tidy logs."""
    return text if len(text) <= n else text[:n] + "…"


_pipeline: CascadePipeline | None = None


def get_pipeline() -> CascadePipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = CascadePipeline()
    return _pipeline
