"""Pydantic v2 request/response models — the public API contract."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Sentiment(str, Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"
    mixed = "mixed"


class Polarity(str, Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"


Source = Literal["classifier", "llm", "judge", "classifier_fallback", "local_llm"]


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Customer text to analyze.")
    require_aspects: bool = Field(
        False, description="Force aspect-level analysis (always escalates to the LLM)."
    )


class BatchRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1)
    require_aspects: bool = False


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #
class Aspect(BaseModel):
    target: str = Field(..., description="The thing the sentiment is about, e.g. 'fees'.")
    polarity: Polarity
    excerpt: str | None = Field(None, description="Span of text supporting the polarity.")


class AnalyzeResponse(BaseModel):
    overall_sentiment: Sentiment
    confidence: float = Field(..., ge=0.0, le=1.0)
    aspects: list[Aspect] = Field(default_factory=list)
    source: Source = Field(..., description="Which stage produced the result (for monitoring).")
    language: str = "en"
    rationale: str | None = Field(None, description="Present only when an LLM stage ran.")


class BatchResponse(BaseModel):
    results: list[AnalyzeResponse]
    escalation_rate: float = Field(..., description="Fraction of inputs that hit an LLM stage.")


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    classifier_model: str
    classifier_loaded: bool
    llm_backend: str
    llm_reachable: bool


# --------------------------------------------------------------------------- #
# Internal — classifier output (not exposed directly)
# --------------------------------------------------------------------------- #
class ClassifierResult(BaseModel):
    label: Polarity
    confidence: float
    distribution: dict[str, float]
    top2_margin: float
