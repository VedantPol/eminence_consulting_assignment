"""
Escalation stage — nuanced, aspect-based analysis for the hard cases.

Two interchangeable backends behind one interface so the stage is replaceable
(brief's requirement to keep `llm.py` abstract):

  * ClaudeBackend          — Anthropic Claude Sonnet 4.6 via forced tool use
                             (structured output guaranteed by `tool_choice`).
  * LocalEscalationBackend — fully offline aspect-based analyzer built on the
                             local classifier + a banking aspect lexicon. Used
                             when no ANTHROPIC_API_KEY is set, and as a runtime
                             fallback if a Claude call fails.

Selection: Claude when an API key is present, else the local backend.
"""
from __future__ import annotations

import asyncio
import re
from typing import Protocol

from pydantic import BaseModel, ValidationError

from .config import Settings, get_settings
from .schemas import AnalyzeResponse, Aspect, Polarity, Sentiment, Source

# --------------------------------------------------------------------------- #
# Shared prompt + tool schema (this rubric is where most of the accuracy lives)
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """\
You are a sentiment analysis engine for an Indian retail bank's customer text
(complaints, feedback, support chats). Classify sentiment precisely.

Rules:
- overall_sentiment is one of: positive, negative, neutral, mixed.
- Use "mixed" only when the text contains clearly opposing sentiments toward
  different aspects. Do not default to mixed for mild text.
- Account for negation and sarcasm; judge the writer's actual stance, not
  surface cue words.
- Identify aspect-level sentiment: the specific thing each sentiment targets
  (e.g. fees, mobile app, branch staff, loan process, interest rate, KYC).
- Handle Hindi/English code-mixed (Hinglish) text.
- Text may contain typed placeholders like [NAME], [ACCOUNT], [PHONE] — treat
  them as masked PII and ignore for sentiment.
- Be conservative with confidence; reserve >0.9 for unambiguous cases.

Return your analysis ONLY via the record_sentiment tool."""

TOOL_NAME = "record_sentiment"
RECORD_SENTIMENT_TOOL = {
    "name": TOOL_NAME,
    "description": "Record the structured sentiment analysis result.",
    "input_schema": {
        "type": "object",
        "properties": {
            "overall_sentiment": {
                "type": "string",
                "enum": ["positive", "negative", "neutral", "mixed"],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "aspects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string"},
                        "polarity": {
                            "type": "string",
                            "enum": ["positive", "negative", "neutral"],
                        },
                        "excerpt": {"type": "string"},
                    },
                    "required": ["target", "polarity"],
                },
            },
            "rationale": {"type": "string"},
            "language": {"type": "string"},
        },
        "required": ["overall_sentiment", "confidence", "aspects", "language"],
    },
}

# --------------------------------------------------------------------------- #
# Few-shot examples — the main tuning surface. Extend with real labelled data.
# Each is rendered as a user -> assistant(tool_use) -> tool_result turn triple.
# --------------------------------------------------------------------------- #
FEW_SHOT_EXAMPLES: list[dict] = [
    {  # negation
        "text": "The app isn't bad at all, honestly works better than HDFC's.",
        "output": {
            "overall_sentiment": "positive", "confidence": 0.82,
            "aspects": [{"target": "mobile app", "polarity": "positive",
                         "excerpt": "works better than HDFC's"}],
            "rationale": "Double negative ('isn't bad') plus favourable comparison = positive.",
            "language": "en"},
    },
    {  # sarcasm
        "text": "Wow, only 45 minutes on hold to be told to call back tomorrow. Brilliant service.",
        "output": {
            "overall_sentiment": "negative", "confidence": 0.9,
            "aspects": [{"target": "customer support", "polarity": "negative",
                         "excerpt": "45 minutes on hold to be told to call back tomorrow"}],
            "rationale": "'Brilliant service' is sarcastic given the 45-minute hold complaint.",
            "language": "en"},
    },
    {  # mixed (the canonical case)
        "text": "Love the app's UI but the fund transfer fees are daylight robbery.",
        "output": {
            "overall_sentiment": "mixed", "confidence": 0.88,
            "aspects": [
                {"target": "mobile app", "polarity": "positive", "excerpt": "Love the app's UI"},
                {"target": "fees", "polarity": "negative",
                 "excerpt": "fund transfer fees are daylight robbery"}],
            "rationale": "Opposing sentiments toward two distinct aspects (app vs fees).",
            "language": "en"},
    },
    {  # Hinglish
        "text": "KYC process bahut slow hai, 3 din ho gaye still pending. Bekaar.",
        "output": {
            "overall_sentiment": "negative", "confidence": 0.86,
            "aspects": [{"target": "KYC process", "polarity": "negative",
                         "excerpt": "KYC process bahut slow hai, 3 din ho gaye still pending"}],
            "rationale": "Code-mixed complaint about a slow, still-pending KYC process.",
            "language": "hi-en"},
    },
    {  # neutral / factual
        "text": "I need to update the registered mobile number on account [ACCOUNT_1].",
        "output": {
            "overall_sentiment": "neutral", "confidence": 0.83,
            "aspects": [], "rationale": "A factual service request with no evaluative content.",
            "language": "en"},
    },
    {  # mild positive — must NOT be 'mixed'
        "text": "Onboarding was smooth, took about ten minutes.",
        "output": {
            "overall_sentiment": "positive", "confidence": 0.8,
            "aspects": [{"target": "onboarding", "polarity": "positive",
                         "excerpt": "Onboarding was smooth"}],
            "rationale": "Mildly positive about onboarding; no opposing aspect, so not mixed.",
            "language": "en"},
    },
]


# --------------------------------------------------------------------------- #
# Internal validation model for the tool output
# --------------------------------------------------------------------------- #
class _ToolOutput(BaseModel):
    overall_sentiment: Sentiment
    confidence: float
    aspects: list[Aspect] = []
    rationale: str | None = None
    language: str = "en"


class EscalationBackend(Protocol):
    source: Source

    async def analyze(self, masked_text: str, require_aspects: bool) -> AnalyzeResponse: ...


# --------------------------------------------------------------------------- #
# Claude backend
# --------------------------------------------------------------------------- #
class ClaudeBackend:
    source: Source = "llm"

    def __init__(self, settings: Settings):
        from anthropic import AsyncAnthropic

        self._settings = settings
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            max_retries=settings.max_retries,   # SDK exponential backoff on 429/5xx
            timeout=settings.llm_timeout,
        )
        self._messages = self._build_fewshot_messages()

    @staticmethod
    def _build_fewshot_messages() -> list[dict]:
        msgs: list[dict] = []
        for i, ex in enumerate(FEW_SHOT_EXAMPLES):
            fid = f"fs_{i}"
            msgs.append({"role": "user", "content": ex["text"]})
            msgs.append({"role": "assistant", "content": [
                {"type": "tool_use", "id": fid, "name": TOOL_NAME, "input": ex["output"]}]})
            msgs.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": fid, "content": "Recorded."}]})
        return msgs

    async def analyze(self, masked_text: str, require_aspects: bool) -> AnalyzeResponse:
        user = masked_text
        if require_aspects:
            user += "\n\n(Provide aspect-level sentiment for every distinct target.)"
        messages = self._messages + [{"role": "user", "content": user}]

        last_err: Exception | None = None
        for _ in range(2):  # one defensive re-ask if the tool output is malformed
            resp = await self._client.messages.create(
                model=self._settings.llm_model,
                max_tokens=self._settings.llm_max_tokens,
                temperature=0,
                thinking={"type": "disabled"},
                system=SYSTEM_PROMPT,
                tools=[RECORD_SENTIMENT_TOOL],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=messages,
            )
            try:
                out = self._parse(resp)
                return AnalyzeResponse(
                    overall_sentiment=out.overall_sentiment,
                    confidence=max(0.0, min(1.0, out.confidence)),
                    aspects=out.aspects,
                    source=self.source,
                    language=out.language or "en",
                    rationale=out.rationale,
                )
            except (ValidationError, ValueError) as e:
                last_err = e
        raise RuntimeError(f"Claude returned unusable output: {last_err}")

    @staticmethod
    def _parse(resp) -> _ToolOutput:
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == TOOL_NAME:
                return _ToolOutput.model_validate(block.input)
        raise ValueError("no record_sentiment tool_use block in response")


# --------------------------------------------------------------------------- #
# Local (offline) aspect-based backend
# --------------------------------------------------------------------------- #
# Banking aspect lexicon: canonical target -> trigger keywords.
_ASPECT_LEXICON: dict[str, list[str]] = {
    "fees": ["fee", "fees", "charge", "charges", "penalty", "hidden cost"],
    "mobile app": ["app", "application", "mobile banking", "ui", "interface"],
    "website": ["website", "net banking", "netbanking", "portal", "online banking"],
    "customer support": ["support", "helpline", "call center", "customer care",
                          "agent", "hold", "ivr", "executive"],
    "branch staff": ["branch", "staff", "teller", "manager", "counter"],
    "loan process": ["loan", "emi", "disbursal", "sanction", "mortgage"],
    "interest rate": ["interest rate", "roi", "interest"],
    "KYC process": ["kyc", "verification", "documents", "re-kyc"],
    "card": ["card", "debit card", "credit card", "atm"],
    "account opening": ["account opening", "onboarding", "open an account", "new account"],
    "transaction": ["transaction", "transfer", "upi", "neft", "imps", "payment", "refund"],
}
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+|(?<=\bbut\b)\s|(?<=\bhowever\b)\s")


def _detect_lang(text: str) -> str:
    try:
        from langdetect import detect, DetectorFactory

        DetectorFactory.seed = 0
        return detect(text)
    except Exception:
        return "en"


class LocalEscalationBackend:
    source: Source = "local_llm"

    def __init__(self, settings: Settings):
        self._settings = settings

    async def analyze(self, masked_text: str, require_aspects: bool) -> AnalyzeResponse:
        # classifier is sync (GPU/CPU bound) — run off the event loop
        return await asyncio.to_thread(self._analyze_sync, masked_text)

    def _analyze_sync(self, text: str) -> AnalyzeResponse:
        from .classifier import get_classifier

        clf = get_classifier()
        clauses = [c.strip() for c in _SENT_SPLIT.split(text) if c.strip()]
        text_lc = text.lower()

        # find aspects present, attach the clause that mentions each
        found: list[tuple[str, str]] = []  # (target, clause)
        for target, keywords in _ASPECT_LEXICON.items():
            for kw in keywords:
                if kw in text_lc:
                    clause = next((c for c in clauses if kw in c.lower()), text)
                    found.append((target, clause))
                    break

        aspects: list[Aspect] = []
        if found:
            results = clf.predict_batch([c for _, c in found])
            for (target, clause), res in zip(found, results):
                aspects.append(Aspect(target=target, polarity=res.label,
                                      excerpt=clause[:160]))

        overall_res = clf.predict(text)
        polarities = {a.polarity for a in aspects}
        if Polarity.positive in polarities and Polarity.negative in polarities:
            overall = Sentiment.mixed
            confidence = 0.7
        else:
            overall = Sentiment(overall_res.label.value)
            confidence = round(min(overall_res.confidence, 0.9), 3)

        rationale = (
            "Local aspect-based analysis: "
            + (", ".join(f"{a.target}={a.polarity.value}" for a in aspects)
               if aspects else "no distinct aspects detected")
            + f"; overall driven by classifier ({overall_res.label.value})."
        )
        return AnalyzeResponse(
            overall_sentiment=overall,
            confidence=confidence,
            aspects=aspects,
            source=self.source,
            language=_detect_lang(text),
            rationale=rationale,
        )


# --------------------------------------------------------------------------- #
# Backend selection
# --------------------------------------------------------------------------- #
_backend: EscalationBackend | None = None


def get_escalation_backend() -> EscalationBackend:
    global _backend
    if _backend is None:
        s = get_settings()
        if s.claude_enabled:
            try:
                _backend = ClaudeBackend(s)
            except Exception:  # SDK import / client init issue -> degrade locally
                _backend = LocalEscalationBackend(s)
        else:
            _backend = LocalEscalationBackend(s)
    return _backend


def backend_name() -> str:
    b = get_escalation_backend()
    return "claude" if isinstance(b, ClaudeBackend) else "local"
