# Cascade Sentiment Service

FastAPI service for banking/fintech text. A local FinBERT classifier handles the easy majority;
low-confidence, mixed, or aspect requests escalate to Claude Sonnet 4.6. PII is masked first. Runs
offline without a key (local fallback handles escalations).

## Run

```bash
pip install -r requirements.txt
cp .env.example .env          # add ANTHROPIC_API_KEY (optional — runs offline without it)
uvicorn app.main:app --reload # http://localhost:8000
```
First run downloads FinBERT (`ProsusAI/finbert`). Uses GPU if available, else CPU.

## Test

```bash
pytest                  # unit tests (no model/network)
python -m tests.eval    # accuracy / F1 / escalation rate on tests/data/eval.csv
```

## Endpoints

| Method | Path | Body |
|---|---|---|
| POST | `/analyze` | `{ "text": "...", "require_aspects": false }` |
| POST | `/analyze/batch` | `{ "texts": ["...", "..."] }` |
| GET | `/health` | — |

`/analyze` returns:
```json
{ "overall_sentiment": "mixed", "confidence": 0.88,
  "aspects": [{ "target": "fees", "polarity": "negative", "excerpt": "fees are robbery" }],
  "source": "llm", "language": "en", "rationale": "..." }
```
`source` is `classifier` | `llm` | `judge` | `classifier_fallback` | `local_llm`.

## Config (`.env`)

| Var | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | blank = local fallback; set = Claude |
| `CLASSIFIER_MODEL` | `ProsusAI/finbert` | local classifier |
| `LLM_MODEL` | `claude-sonnet-4-6` | escalation model |
| `CONF_THRESHOLD` | `0.85` | escalate below this confidence |
| `MARGIN_THRESHOLD` | `0.15` | escalate if top-2 margin below this |
| `MAX_LLM_CONCURRENCY` | `5` | bounded in-flight Claude calls |
| `ENABLE_JUDGE` | `false` | second-opinion pass on disagreement |
