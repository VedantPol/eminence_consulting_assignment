# Methodology — Reputation Intelligence Workflow
**Brand:** ICICI Prudential AMC (BFSI) · **Dataset:** 100 digital mentions · *(≤ 3 pages)*

A fully automated pipeline turns raw digital mentions into a cleaned, classified,
and enriched dataset plus executive reputation metrics. No record is classified
by hand — every label comes from a model.

```
Dataset.xlsx → standardize → dedup → relevance filter → classify
            → LLM escalation → enrich → intelligence → outputs/
```

---

## 1. Approach to data cleaning & classification

### Cleaning & processing
- **Standardization** — fix the messy provided sentiment casing (`positive`/`Positive`/`Negative` → `{Positive, Neutral, Negative}`); build a **unified text blob** (Title + Opening Text + Hit Sentence, since no single field is complete); parse dates; derive `channel`, `source_tier`, `language`, and brand-salience tier. HTML-unescape, strip URLs/zero-width characters, collapse whitespace.
- **Deduplication** — on **normalized content, not URL**. The Play-Store app URL repeats ~15× but each row is a *distinct* review, so URL-dedup would destroy real signal. Three passes: exact content, embedding near-duplicate (MiniLM cosine ≥ 0.95), and **cross-source headline syndication** (same headline across different outlets). The highest-reach copy is kept and the dropped copies' reach is consolidated into it.
- **Removal of irrelevant records** — two-tier: a rule (brand/person mentioned, or first-party app/review channel) then a semantic finance-relevance gate. Clear off-topic noise (e.g. *"Best MBA Colleges in Kalyan"*) is dropped; borderline generic listicles are kept but tagged `peripheral` so they can be excluded from headline metrics.
- Every dropped row is preserved in an **audit sheet** with the reason.

**Funnel:** 100 raw → 4 duplicates → 1 irrelevant → **95 classified** (reconciles to 100).

### Classification (driver · sub-driver · sentiment)
A **cascade** keeps it scalable and accurate:
1. **Cheap local pass.** A zero-shot NLI classifier (DeBERTa-v3) scores each record against rich natural-language hypotheses for the 8 sub-drivers; the parent **driver is derived from the chosen sub-driver** so the two can never disagree. Sub-driver is always populated; a confidence + `low_confidence` flag carries uncertainty.
2. **LLM escalation.** The ~24 low-confidence rows escalate to **Claude Sonnet 4.6** (forced tool use → guaranteed structured output, the full taxonomy injected into the system prompt). Offline fallback keeps zero-shot labels if the API is unavailable.
3. **Sentiment** uses a **channel-aware hybrid** — FinBERT for financial news, a Twitter-RoBERTa model for app-store/Reddit/social text (FinBERT alone misread blunt app complaints as neutral; the hybrid lifted negative recall from 2/10 → 8/10).

### Validation (the "is it right?" evidence)
Claude Sonnet 4.6 also labels **all 95 rows as an independent silver-gold reference**. Measured accuracy of the cheap classifier: **driver 86.3 % (macro-F1 0.80)**, **sub-driver 83.2 % (macro-F1 0.83)**. Sentiment agreement with the provided labels is **70.5 %** — and notably, Claude agrees with those labels only **47 %**, showing the provided labels are themselves a noisy reference rather than ground truth.

### Intelligence layer
Net Sentiment, **Share of Voice** vs a competitor gazetteer, a composite **Reputation Health Score (0–100)**, Claude-named discussion themes, a reach-weighted **risk queue**, spokesperson sentiment, and driver × sentiment breakdowns — all written to `insights.json` for the dashboard.

---

## 2. Tools, models & frameworks
| Area | Choice |
|------|--------|
| Language / data | Python, pandas, scikit-learn, NumPy |
| NLP | HuggingFace `transformers`, `sentence-transformers`, KeyBERT |
| Sentiment | `ProsusAI/finbert` (news) + `cardiffnlp/twitter-roberta-base-sentiment-latest` (social) |
| Driver / sub-driver | `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` (zero-shot NLI) |
| Hard-case + validation + themes | **Claude Sonnet 4.6** (`claude-sonnet-4-6`) via the Anthropic SDK, forced tool use |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (dedup, relevance, themes) |
| Dashboard | Next.js 14 + TypeScript + Tailwind + Recharts, deployed on Vercel |
| Compute | Auto-detects GPU (CUDA) / CPU; runs fully offline if no API key |

Runs end-to-end with a single command (`./run.sh`) in ~45 s on a GPU.

---

## 3. Key assumptions
- The provided `Sentiment` column is a **QA reference, not ground truth** (it is messy and even a frontier model diverges from it), so sentiment is re-classified and agreement is reported.
- The dataset contained **100 records** (the brief said "approximately 150").
- **App-store / review** rows are relevant UX signal even when they don't name the brand.
- Each record maps to **one most-relevant** driver/sub-driver.
- Claude is an acceptable **silver-gold** annotator for validation (LLM reference, not human-labelled).
- Generic "best funds" listicles that came from a brand-monitoring pull may still be brand-relevant, so they are tagged rather than dropped (precision-first).

---

## 4. Limitations
- **Small corpus (100 rows).** Zero-shot hypotheses were tuned on this data; generalisation to a fresh pull is untested.
- **No human gold set.** Reported accuracy is against an LLM silver-gold reference, which can share blind spots with the escalation model.
- **Sentiment 70.5 % agreement** reflects a labelling-philosophy gap (neutral-vs-positive on factual reporting), not pure error — but without a human gold set this can't be fully separated.
- **Themes** on short, homogeneous text cluster weakly (silhouette ≈ 0.06); this is mitigated by LLM-named themes but those depend on the API.
- **Relevance filter is deliberately lenient** (keeps low-salience listicles, flagged `peripheral`) to avoid dropping true mentions; a stricter setting would trade recall for precision.
- **LLM stage needs network + API key**; the pipeline degrades to fully-offline zero-shot otherwise.
- **Reach** is missing for ~35 % of rows, so reach-weighted metrics treat unknowns conservatively.
