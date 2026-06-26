"""
Stage 4b — LLM classification escalation (Claude Sonnet 4.6).

The offline zero-shot classifier resolves the easy majority; rows where it is
uncertain (sub-driver confidence < threshold) are escalated here for a nuanced
re-classification. Structured output is GUARANTEED via forced tool use, the full
taxonomy is injected into the system prompt, and `driver` is derived from the
chosen `sub_driver` so the two can never disagree.

Only PII-free public media text is sent. On any API failure the row keeps its
zero-shot label (caller marks it `zero_shot_fallback`) — the pipeline still runs
fully offline if no key is present.
"""
from __future__ import annotations

import concurrent.futures as cf
import logging

from . import config as C

log = logging.getLogger("llm_classify")

TOOL_NAME = "classify_record"


def _render_taxonomy() -> str:
    lines = []
    for driver, subs in C.TAXONOMY.items():
        lines.append(f"\n{driver}:")
        for sub, desc in subs.items():
            lines.append(f"  - {sub}: {desc}")
    return "\n".join(lines)


SYSTEM_PROMPT = f"""\
You are a reputation-intelligence analyst for {C.BRAND}, an Indian mutual-fund
house (BFSI). For each media mention, assign the SINGLE most relevant reputation
sub-driver from the framework below, and the sentiment toward the brand.

CLASSIFICATION FRAMEWORK (Driver -> Sub-driver: what it covers):
{_render_taxonomy()}

Rules:
- Choose exactly ONE sub-driver — the dominant theme of the mention.
- "Thought Leadership" = expert/CIO market commentary & outlook. "Product &
  Service Quality" = fund returns/performance, best-fund comparisons, rankings.
  "Product Strategy" = a NEW fund/NFO/SIP launch or pricing. Distinguish these
  carefully — performance commentary is not the same as a product launch.
- For generic "best mutual funds" listicles, classify by the dominant topic
  (usually Product & Service Quality), not Thought Leadership.
- Sentiment is toward {C.BRAND} specifically: Positive, Neutral, or Negative.
  Factual/market-neutral reporting is Neutral. Account for negation and sarcasm.
- Placeholders or truncation may appear; judge from what is present.
- Be calibrated: reserve confidence > 0.9 for unambiguous cases.

Respond ONLY via the classify_record tool."""

CLASSIFY_TOOL = {
    "name": TOOL_NAME,
    "description": "Record the reputation classification of one media mention.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sub_driver": {"type": "string", "enum": C.SUBDRIVERS},
            "sentiment": {"type": "string", "enum": ["Positive", "Neutral", "Negative"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": {"type": "string"},
        },
        "required": ["sub_driver", "sentiment", "confidence"],
    },
}


class ClaudeClassifier:
    def __init__(self):
        import anthropic

        self.model = C.LLM_MODEL
        self._client = anthropic.Anthropic(
            api_key=C.ANTHROPIC_API_KEY, max_retries=3, timeout=30
        )

    def classify(self, text: str) -> dict | None:
        """Return {driver, sub_driver, sentiment, confidence, rationale} or None on failure."""
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=400,
                temperature=0,
                thinking={"type": "disabled"},
                system=SYSTEM_PROMPT,
                tools=[CLASSIFY_TOOL],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=[{"role": "user", "content": text[:4000]}],
            )
            data = self._parse(resp)
        except Exception as e:  # transport / validation -> caller falls back
            log.warning("LLM classify failed: %s", e)
            return None

        sub = data["sub_driver"]
        return {
            "driver": C.SUB_TO_DRIVER[sub],          # derived -> always consistent
            "sub_driver": sub,
            "sentiment": data["sentiment"],
            "confidence": float(max(0.0, min(1.0, data["confidence"]))),
            "rationale": data.get("rationale", ""),
        }

    @staticmethod
    def _parse(resp) -> dict:
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == TOOL_NAME:
                d = block.input
                if d.get("sub_driver") in C.SUBDRIVERS and d.get("sentiment") in (
                    "Positive", "Neutral", "Negative"
                ):
                    return d
        raise ValueError("no valid classify_record tool_use block")

    def classify_many(self, texts: list[str], max_workers: int = 5) -> list[dict | None]:
        """Concurrent (bounded) classification, preserving input order."""
        results: list[dict | None] = [None] * len(texts)
        with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(self.classify, t): i for i, t in enumerate(texts)}
            for fut in cf.as_completed(futs):
                results[futs[fut]] = fut.result()
        return results
