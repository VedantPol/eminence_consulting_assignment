# Cascade Sentiment Analysis Service

A production sentiment service for banking/fintech customer text. A **fast local
classifier** handles the easy majority of inputs; low-confidence, mixed, or
aspect-requested inputs **escalate to Claude Sonnet 4.6** for nuanced,
aspect-based reasoning (negation, sarcasm, mixed sentiment, code-mixed Hinglish).
An optional LLM-as-judge resolves classifier↔LLM disagreements.

```
text → PII mask → fast classifier → confidence gate ─┬─ high conf → return
                                                     └─ low/mixed/aspects → Claude (tool use)
                                                                              └─ optional judge → return
```

## Runs now without a key

The brief's LLM stage requires `ANTHROPIC_API_KEY`. Until that's provided the
service runs **fully offline**: with no key, escalations are handled by a local
aspect-based backend (`source: "local_llm"`). Set the key and it transparently
switches to Claude (`source: "llm"`) — no code change. `app/llm.py` is kept
behind a clean `EscalationBackend` interface so the stage is replaceable.

## Setup

```bash
# from the project root, in an env with torch installed
pip install -r requirements.txt
cp .env.example .env          # optionally add ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

First run downloads the classifier model (`ProsusAI/finbert`); GPU is used if
available, else CPU.

## API

`POST /analyze`
```json
{ "text": "Love the app but the fees are robbery.", "require_aspects": false }
```
```json
{
  "overall_sentiment": "mixed",
  "confidence": 0.88,
  "aspects": [
    { "target": "mobile app", "polarity": "positive", "excerpt": "Love the app" },
    { "target": "fees", "polarity": "negative", "excerpt": "fees are robbery" }
  ],
  "source": "llm",
  "language": "en",
  "rationale": "Opposing sentiment toward app vs fees."
}
```

`POST /analyze/batch` — `{ "texts": [...], "require_aspects": false }` → results +
`escalation_rate`. The classifier runs in one batched forward pass; LLM
escalations run concurrently (bounded by `MAX_LLM_CONCURRENCY`).

`GET /health` → classifier loaded + which LLM backend is active.

`source` is always returned so you can monitor escalation rate:
`classifier` · `llm` · `judge` · `classifier_fallback` · `local_llm`.

## How it works

| Stage | File | Notes |
|-------|------|-------|
| PII masking | `app/pii.py` | Regex for email/phone/PAN/Aadhaar/card/account/IFSC + optional spaCy NER for names. Deterministic. Runs **before any model call**; only masked text is logged. |
| Fast classifier | `app/classifier.py` | HF `transformers`, configurable model (default FinBERT). Returns label, confidence, full distribution, and `top2_margin`. GPU if available. |
| Confidence gate | `app/pipeline.py` | Escalate if `confidence < CONF_THRESHOLD`, `top2_margin < MARGIN_THRESHOLD`, `require_aspects`, or (optional) length. |
| LLM stage | `app/llm.py` | Claude Sonnet 4.6 via **forced tool use** (`tool_choice` → `record_sentiment`) so output is schema-guaranteed; rubric system prompt + few-shot examples are the tuning surface. Local backend mirrors the same contract offline. |
| Judge | `app/judge.py` | Optional second Claude call on disagreement (`ENABLE_JUDGE=true`). |

**Resilience:** the Anthropic SDK retries 429/5xx with exponential backoff
(`max_retries`); on final failure (or malformed tool output after one re-ask)
the request falls back to the classifier verdict (`source: "classifier_fallback"`)
instead of erroring. LLM calls are timeout-bounded.

## Config (`.env`)

| Var | Default | Meaning |
|-----|---------|---------|
| `ANTHROPIC_API_KEY` | — | Enables the Claude backend; blank = local fallback |
| `LLM_MODEL` | `claude-sonnet-4-6` | Escalation model |
| `CLASSIFIER_MODEL` | `ProsusAI/finbert` | Swap to `cardiffnlp/twitter-roberta-base-sentiment-latest` for social text |
| `CONF_THRESHOLD` | `0.85` | Escalate below this confidence |
| `MARGIN_THRESHOLD` | `0.15` | Escalate if top-2 margin below this |
| `ENABLE_JUDGE` | `false` | Judge pass on disagreement |
| `MAX_LLM_CONCURRENCY` | `5` | Bounded in-flight Anthropic calls |
| `ESCALATE_ON_LENGTH` | `0` | `>0` escalates long text |

## Tests & benchmark

```bash
pytest                 # unit tests (PII, gate logic, routing, tool parsing) — no model/network
python -m tests.eval   # accuracy / macro-F1 / escalation rate / latency on tests/data/eval.csv
```

The eval harness reports classifier-only vs cascade so you can tune
`CONF_THRESHOLD` against the cost/accuracy tradeoff. With a key set it also
exercises the Claude path; without one, escalations use the local backend.

## Notes

- Only PII-masked text ever reaches the Anthropic API.
- The rubric (`SYSTEM_PROMPT`) and `FEW_SHOT_EXAMPLES` in `app/llm.py` are the
  main accuracy levers — extend the few-shot list with real labelled hard cases.
- For full data residency, swap the Claude backend for a self-hosted model behind
  the same `EscalationBackend` interface (an optional `LOCAL_LLM_BASE_URL` hook is
  already in config).
