# Reputation Intelligence Workflow — Eminence Assignment

A mini reputation-intelligence workflow for a BFSI brand (**ICICI Prudential AMC**):
it processes, classifies, analyses, and presents ~100 digital mentions — fully
automated, no manual classification.

### 🔗 Live dashboard → **https://eminence-consulting.vedant-home-server.in/#overview**

---

## Submission map (everything the brief asks for)

| Requirement | Where | Status |
|---|---|---|
| **Source code** | this repo (`pipeline/`, `dashboard/`) | ✅ |
| **Processed dataset** (cleaned + classified) | [`outputs/cleaned_classified.xlsx`](outputs/cleaned_classified.xlsx) · [`classified.csv`](outputs/classified.csv) | ✅ |
| **Dashboard** | [`dashboard/`](dashboard/) — live link above | ✅ |
| **README with setup** | this file | ✅ |
| **Methodology document** (≤3 pp) | [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) | ✅ |
| **Part 1 — Processing, Classification & Intelligence** (60%) | `pipeline/` → `outputs/` | ✅ |
| **Part 2 — Dashboard / UI** (30%) | `dashboard/` | ✅ |
| **Part 3 — Data Collection & Scalability** (10%) | [`docs/PART3_DATA_COLLECTION_SCALABILITY.md`](docs/PART3_DATA_COLLECTION_SCALABILITY.md) | ✅ |
| Exploratory analysis | [`EDA.ipynb`](EDA.ipynb) | ✅ |

---

## Project structure
```
.
├── run.sh                 # one-command entry point for Part 1
├── run_phase1.py          # pipeline orchestrator
├── pipeline/              # Part 1 — one file per stage
│   ├── preprocess.py      #   standardize
│   ├── dedup.py           #   deduplicate (content + syndication)
│   ├── relevance.py       #   remove irrelevant
│   ├── classify.py        #   zero-shot driver/sub-driver + hybrid sentiment
│   ├── llm_classify.py    #   Claude escalation + silver-gold validation
│   ├── enrich.py          #   entities, keyphrases, risk
│   ├── themes_llm.py      #   Claude-named themes
│   ├── intelligence.py    #   SoV, Reputation Health Score, metrics
│   ├── config.py          #   taxonomy, gazetteers, weights (the "knowledge")
│   └── device.py          #   GPU/CPU auto-detect
├── outputs/               # the processed dataset + insights.json + report
├── dashboard/             # Part 2 — Next.js dashboard (reads outputs as static JSON)
├── docs/                  # Methodology + Part 3 write-up
├── EDA.ipynb              # exploratory data analysis
└── Dataset.xlsx           # provided input
```

---

## Part 1 — run the pipeline

```bash
./run.sh                       # installs deps, downloads models, runs end-to-end
# or:  pip install -r requirements.txt && python run_phase1.py
```
- **~8 s on GPU / ~5 min on CPU** (offline); **~45 s** with the Claude escalation enabled.
- **Optional Claude escalation:** put `ANTHROPIC_API_KEY=sk-ant-...` in a `.env` file
  (git-ignored). With no key the pipeline runs **100 % offline** (local models only).

**What it does:** `standardize → dedup → relevance filter → classify (FinBERT/social
sentiment + DeBERTa zero-shot driver/sub-driver) → Claude escalation for low-confidence
rows → enrich → intelligence`. Every record gets **driver + sub-driver + sentiment**
(no blanks); every dropped row is kept in an audit sheet.

**Outputs (`outputs/`):** `cleaned_classified.xlsx` (classified data + audit + insight
sheets), `classified.csv` / `classified.json`, `insights.json` (dashboard data),
`pipeline_report.md`.

**Headline results:** 100 → 4 dupes → 1 irrelevant → **95 classified** · Reputation
Health **60.1/100** · Share of Voice **82.4 %** · driver accuracy **86.3 %** /
sub-driver **83.2 %** (vs a Claude silver-gold reference).

---

## Part 2 — run the dashboard

```bash
cd dashboard
npm install
npm run dev                    # http://localhost:3000
```
Three sections per the brief — **Overview** (KPIs, Reputation Health gauge, sentiment /
driver / sub-parameter distributions, named themes), **Content Explorer** (search +
filter by driver / sub-driver / sentiment / channel, click a row for the original
content), and **Insights** (key findings, positive vs negative drivers, risk queue,
spokesperson sentiment).

It reads the pre-computed `outputs/insights.json` + `classified.json` as **static data**
— no backend. Refresh after re-running Part 1:
`cp ../outputs/{insights,classified}.json data/`.

**Deploy (Vercel):** import the repo → set **Root Directory = `dashboard`** → deploy
(framework auto-detected; build command `next build`; no env vars needed).

---

## Models used
FinBERT · Twitter-RoBERTa (sentiment) · DeBERTa-v3 zero-shot (driver/sub-driver) ·
MiniLM embeddings · **Claude Sonnet 4.6** (hard cases, validation, theme naming).
See [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) for the full rationale, assumptions, and limitations.

> **Bonus (not required by the brief):** [`sentiment-cascade/`](sentiment-cascade/) is a
> standalone FastAPI cascade-sentiment microservice (local classifier → Claude for hard
> cases, with PII masking and tests) — included as an example of productionising the
> classification approach.
