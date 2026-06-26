"""FastAPI app exposing the cascade sentiment service."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .config import get_settings
from .llm import backend_name
from .pipeline import get_pipeline
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    BatchRequest,
    BatchResponse,
    HealthResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the classifier (and select the LLM backend) once at startup.
    s = get_settings()
    log.info("Loading classifier '%s' and selecting LLM backend...", s.classifier_model)
    get_pipeline()
    log.info("Ready. LLM backend=%s (claude_enabled=%s)", backend_name(), s.claude_enabled)
    yield


app = FastAPI(title="Cascade Sentiment Analysis", version="1.0.0", lifespan=lifespan)


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    try:
        return await get_pipeline().analyze_one(req.text, req.require_aspects)
    except Exception as e:  # never leak internals / PII
        log.exception("analyze failed")
        raise HTTPException(status_code=500, detail="analysis failed") from e


@app.post("/analyze/batch", response_model=BatchResponse)
async def analyze_batch(req: BatchRequest) -> BatchResponse:
    try:
        results, rate = await get_pipeline().analyze_batch(req.texts, req.require_aspects)
        return BatchResponse(results=results, escalation_rate=rate)
    except Exception as e:
        log.exception("batch analyze failed")
        raise HTTPException(status_code=500, detail="batch analysis failed") from e


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    s = get_settings()
    classifier_loaded = False
    try:
        get_pipeline().classifier.predict("ok")
        classifier_loaded = True
    except Exception:
        pass
    # We report whether Claude is configured; we do not spend a token pinging it.
    llm_reachable = s.claude_enabled if backend_name() == "claude" else True
    return HealthResponse(
        status="ok" if classifier_loaded else "degraded",
        classifier_model=s.classifier_model,
        classifier_loaded=classifier_loaded,
        llm_backend=backend_name(),
        llm_reachable=llm_reachable,
    )
