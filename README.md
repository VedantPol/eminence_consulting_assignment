# Reputation Intelligence Workflow

A mini reputation-intelligence pipeline for a BFSI brand, **ICICI Prudential AMC**. It cleans,
classifies, and analyses ~100 digital mentions, then presents them in a dashboard. Nothing is labelled
by hand.

### Live dashboard → **https://eminence-consulting.vedant-home-server.in/#overview**

## What's where

| Deliverable | Location |
|---|---|
| Source code | `pipeline/` (Part 1), `dashboard/` (Part 2) |
| Processed dataset | [`outputs/cleaned_classified.xlsx`](outputs/cleaned_classified.xlsx), [`classified.csv`](outputs/classified.csv) |
| Dashboard | [`dashboard/`](dashboard/) — live link above |
| Methodology | [PDF](docs/Methodology_final.pdf) |
| Part 3 (collection & scalability) | [PDF](docs/PART3_DATA_COLLECTION_SCALABILITY_final.pdf)|
| Exploratory analysis | [`EDA.ipynb`](EDA.ipynb) |

## Layout

```
run.sh                  one command to run Part 1
run_phase1.py           pipeline orchestrator
pipeline/               one file per stage
  preprocess.py           standardize
  dedup.py                deduplicate (content + syndication)
  relevance.py            drop irrelevant
  classify.py             zero-shot driver/sub-driver + hybrid sentiment
  llm_classify.py         Claude escalation + accuracy validation
  themes_llm.py           Claude-named themes
  enrich.py               entities, keyphrases, risk
  intelligence.py         share of voice, Reputation Health Score, metrics
  config.py               taxonomy, gazetteers, weights
outputs/                classified dataset + insights.json + report
dashboard/              Next.js dashboard (reads outputs as static JSON)
docs/                   methodology + Part 3
```

## Part 1 — the pipeline

```bash
./run.sh                       # installs deps, fetches models, runs end to end
# or: pip install -r requirements.txt && python run_phase1.py
```

It standardizes the data, deduplicates on content, drops irrelevant records, classifies every mention
into a driver, sub-driver, and sentiment, sends low-confidence cases to Claude Sonnet 4.6, then builds
the reputation metrics. Add `ANTHROPIC_API_KEY=sk-ant-...` to a `.env` file (git-ignored) to enable the
Claude stage; without a key it runs fully offline on the local models.

Output lands in `outputs/`: `cleaned_classified.xlsx` (the labelled data plus audit and insight sheets),
`classified.csv`/`.json`, `insights.json` for the dashboard, and `pipeline_report.md`.

Results: 100 raw → 4 duplicates → 1 irrelevant → **95 classified**. Reputation Health **60.1/100**,
share of voice **82.4%**, driver accuracy **87%** and sub-driver **84%** against a Claude reference.

## Part 2 — the dashboard

```bash
cd dashboard && npm install && npm run dev      # http://localhost:3000
```

Three views: **Overview** (KPIs, Reputation Health gauge, sentiment / driver / sub-parameter
distributions, named themes), **Content Explorer** (search and filter by driver, sub-driver, sentiment,
channel, theme, and date; click a row for the original text and source; export the filtered set to CSV),
and **Insights** (key findings, strongest and weakest drivers, risk queue, spokesperson sentiment).
Clicking any chart in Overview drills into the Explorer with that filter applied.

It reads the pre-computed `insights.json` and `classified.json` as static files, so there is no backend.
Refresh after re-running Part 1 with `cp ../outputs/{insights,classified}.json data/`.

To deploy on Vercel: import the repo, set the root directory to `dashboard`, and deploy. Next.js is
detected automatically and no environment variables are needed.

## Models

FinBERT and Twitter-RoBERTa for sentiment, DeBERTa-v3 zero-shot for driver and sub-driver, MiniLM for
embeddings, and Claude Sonnet 4.6 for hard cases, accuracy validation, and theme naming. The
[methodology](docs/METHODOLOGY.md) explains the choices, assumptions, and limitations.

> Not part of the brief: [`sentiment-cascade/`](sentiment-cascade/) is a standalone FastAPI service that
> productionises the classification idea (local model first, Claude for hard cases, PII masking, tests).
