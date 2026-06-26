# Reputation Intelligence — Phase 1 (Data Processing, Classification & Intelligence)

Turns ~100 raw digital mentions of **ICICI Prudential AMC** (`Dataset.xlsx`) into a
**cleaned, classified, and enriched dataset** plus executive reputation metrics —
the deliverable for Part 1 of the assignment.

## Run it (one command)

```bash
./run.sh
```

`run.sh` activates the environment, installs anything missing, downloads the
models once, and runs the pipeline end-to-end (~8s on GPU, ~5 min on CPU; ~40s
with the Claude escalation enabled). Equivalent manual run:

```bash
pip install -r requirements.txt
python run_phase1.py
```

**Optional — Claude escalation.** Drop an API key in `.env` and the pipeline
sends *only* its low-confidence classifications to Claude Sonnet 4.6 for a
nuanced re-read. With no key it runs **100% offline** (local models only).

```bash
# .env  (gitignored — never committed)
ANTHROPIC_API_KEY=sk-ant-...
```

## What it does — the assignment's Part 1, end to end

| # | Stage | File | What happens |
|---|-------|------|--------------|
| 1 | **Standardize** | `pipeline/preprocess.py` | fix messy sentiment casing → {Positive,Neutral,Negative}; build a unified text blob (Title+Opening+Hit Sentence); parse dates; derive channel, source-tier, language, brand-salience |
| 2 | **Deduplicate** | `pipeline/dedup.py` | exact-content + embedding near-dup + **cross-source headline syndication**; keeps the highest-reach copy and consolidates reach. *Content-based, not URL-based*, so distinct app reviews are preserved |
| 3 | **Remove irrelevant** | `pipeline/relevance.py` | two-tier filter (brand/person/app-channel rule → semantic finance gate); drops off-topic noise; tiers the rest (headline / body / first_party / peripheral) |
| 4 | **Classify** | `pipeline/classify.py` | **driver + sub-driver** (DeBERTa zero-shot over the 8-sub-driver framework) and **sentiment** (FinBERT for news, a social model for app/Reddit) |
| 4b | **LLM escalation** | `pipeline/llm_classify.py` | low-confidence driver/sub-driver rows → **Claude Sonnet 4.6** (forced tool use, full taxonomy); offline fallback if unavailable |
| 5 | **Enrich** | `pipeline/enrich.py` | entities/competitors, keyphrases, themes, reach-weighted **risk queue** |
| 6 | **Intelligence** | `pipeline/intelligence.py` | Net Sentiment, **Share of Voice**, composite **Reputation Health Score**, breakdowns, sentiment QA vs the provided labels |

Every record is classified into **driver + sub-driver + sentiment** (no blanks),
and every dropped row is kept in an audit sheet with the reason.

## Classification framework (3 drivers / 8 sub-drivers)

- **Brand Perception** → Thought Leadership · Product Strategy · Brand Visibility & Marketing
- **User Experience** → Product & Service Quality · Customer Support & Complaint Resolution · Digital & Omnichannel Experience
- **Responsible Business Practices** → Regulatory Compliance & Ethical Governance · Social Impact & Community (CSR)

## Outputs (`outputs/`)

- **`cleaned_classified.xlsx`** — the processed dataset. Sheets: `classified` (all
  records + labels, confidences, themes, entities, risk), `driver_breakdown`,
  `themes`, `risk_queue`, `removed_duplicates`, `removed_irrelevant` (audit trails).
- `classified.csv` — flat version of the classified sheet.
- `insights.json` — all metrics for the Part-2 dashboard.
- `pipeline_report.md` — human-readable run summary.

## Models (local, run offline after first download)

| Task | Model |
|------|-------|
| Sentiment (news) | `ProsusAI/finbert` |
| Sentiment (app/social) | `cardiffnlp/twitter-roberta-base-sentiment-latest` |
| Driver / sub-driver | `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` |
| Hard-case escalation | `claude-sonnet-4-6` (only if API key set) |
| Emotion | `j-hartmann/emotion-english-distilroberta-base` |
| Embeddings (dedup/themes) | `sentence-transformers/all-MiniLM-L6-v2` |

## Design notes

- **Sub-driver is always populated** (never blank); uncertainty is carried by a
  confidence + `low_confidence` flag, and those rows are what escalate to Claude.
- The provided `Sentiment` labels are treated as a **QA reference** (agreement
  reported), not ground truth — we re-classify and compare.
- The Claude escalation corrects only the flagged weakness (driver/sub-driver); it
  does **not** override sentiment (which is validated against the provided labels).
- Exploratory analysis is in `EDA.ipynb`.
