"""
Optional LLM-as-judge pass (off by default, ENABLE_JUDGE=true to enable).

When the fast classifier and the LLM disagree on overall_sentiment, a second
Claude call sees the text plus both verdicts and decides which is correct. Only
meaningful with the Claude backend; with the local backend the pipeline skips it.
"""
from __future__ import annotations

from pydantic import BaseModel, ValidationError

from .config import Settings
from .schemas import AnalyzeResponse, Sentiment

JUDGE_SYSTEM = """\
You are a senior sentiment-analysis adjudicator for an Indian retail bank.
A fast classifier and a detailed analyzer disagreed on the overall sentiment of
a customer message. Decide the correct overall sentiment, accounting for
negation, sarcasm, and mixed/aspect-level sentiment. Be decisive and brief.
Return your decision ONLY via the judge_verdict tool."""

JUDGE_TOOL_NAME = "judge_verdict"
JUDGE_TOOL = {
    "name": JUDGE_TOOL_NAME,
    "description": "Record the adjudicated overall sentiment.",
    "input_schema": {
        "type": "object",
        "properties": {
            "final_sentiment": {
                "type": "string",
                "enum": ["positive", "negative", "neutral", "mixed"],
            },
            "winner": {"type": "string", "enum": ["classifier", "analyzer", "neither"]},
            "justification": {"type": "string"},
        },
        "required": ["final_sentiment", "winner", "justification"],
    },
}


class _Verdict(BaseModel):
    final_sentiment: Sentiment
    winner: str
    justification: str


class Judge:
    def __init__(self, settings: Settings):
        from anthropic import AsyncAnthropic

        self._settings = settings
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            max_retries=settings.max_retries,
            timeout=settings.llm_timeout,
        )

    async def adjudicate(
        self, masked_text: str, classifier_label: str, llm_resp: AnalyzeResponse
    ) -> AnalyzeResponse:
        prompt = (
            f"Customer message:\n{masked_text}\n\n"
            f"Fast classifier verdict: {classifier_label}\n"
            f"Detailed analyzer verdict: {llm_resp.overall_sentiment.value} "
            f"(rationale: {llm_resp.rationale})\n\n"
            "Which overall sentiment is correct?"
        )
        resp = await self._client.messages.create(
            model=self._settings.llm_model,
            max_tokens=512,
            temperature=0,
            thinking={"type": "disabled"},
            system=JUDGE_SYSTEM,
            tools=[JUDGE_TOOL],
            tool_choice={"type": "tool", "name": JUDGE_TOOL_NAME},
            messages=[{"role": "user", "content": prompt}],
        )
        verdict = self._parse(resp)
        # Keep the analyzer's aspect breakdown; the judge only revises the overall.
        return AnalyzeResponse(
            overall_sentiment=verdict.final_sentiment,
            confidence=llm_resp.confidence,
            aspects=llm_resp.aspects,
            source="judge",
            language=llm_resp.language,
            rationale=f"Judge ({verdict.winner}): {verdict.justification}",
        )

    @staticmethod
    def _parse(resp) -> _Verdict:
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == JUDGE_TOOL_NAME:
                return _Verdict.model_validate(block.input)
        raise ValueError("no judge_verdict tool_use block in response")
