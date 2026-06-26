# Part 3 — Automated Data Collection & Scalability Approach
*How I would automate daily collection of mentions from news websites, Reddit, and X/Twitter. (No code; ≤ 2 pages.)*

## Architecture at a glance
```
 Sources                Ingestion (workers)        Queue        Processing             Storage / Serving
 ───────                ───────────────────        ─────        ──────────             ─────────────────
 News (RSS/API/scrape) ─┐                                     ┌─ dedup + quality ─┐
 Reddit (API)          ─┼─► collectors (per source) ─► Kafka ─┼─ classify cascade ─┼─► Postgres + S3 (raw)
 X/Twitter (API)       ─┘     (scheduled, rate-limited)        └─ enrich/metrics  ─┘    + pgvector + warehouse
```
The Part-1 pipeline becomes the **"Processing"** block, run continuously on a stream instead of a one-off file.

## 1. Data collection approach
- **News websites.** Prefer structured feeds: **RSS/Atom** and sitemaps where available; **Google News RSS / GDELT** for broad discovery; a brand-keyword query against a news API (NewsAPI, Bing News) as a supplement. For sites without feeds, scheduled **Scrapy** spiders, escalating to **Playwright** for JavaScript-rendered pages. Each source has a small adapter that maps its payload to a common schema.
- **Reddit.** The official Reddit API via **PRAW** — search brand keywords across relevant subreddits (r/MutualFundsIndia, r/IndiaInvestments, …) and poll `new` submissions + comments on a schedule.
- **X/Twitter.** The X API v2 **filtered stream / recent-search** with brand keyword + cashtag rules; given X's cost and access limits, keep a **commercial fallback** (Apify, Brandwatch) behind the same adapter interface.
- **Orchestration.** A scheduler (**Airflow / cloud scheduler / cron**) fires per-source collectors **daily** (or near-real-time for X). Collectors are stateless workers that emit normalized records to a queue. A shared **brand-match rule** (keyword + entity + semantic gate, reused from Part 1's relevance filter) drops obvious noise at the edge.
- **Common schema:** `{id, date, source, source_tier, url, title, text, channel, reach?, raw_payload}`.

## 2. Storage approach
- **Raw landing zone (S3 / object storage).** Every raw payload is stored immutably and partitioned by `source/date` — this makes the pipeline **replayable** (re-run classification without re-scraping) and is the audit of record.
- **Operational store (PostgreSQL).** Normalized mentions + their classifications (driver, sub-driver, sentiment, confidence, themes, risk), partitioned by date and upserted by content key. **pgvector** holds the embeddings used for dedup and semantic search.
- **Analytics (warehouse: BigQuery / Snowflake).** Aggregations feed the dashboard's `insights.json`-equivalent and BI tooling at scale.
- Classifications are versioned with the model + prompt version so results are reproducible and back-fillable.

## 3. Handling duplicates & data-quality issues
- **Deduplication (reuse Part 1's logic at stream scale):** URL canonicalization → exact content hash → **embedding near-duplicate** (cosine ≥ 0.95 over a rolling time window via pgvector) → **cross-source syndication** (same headline across outlets). Upsert-by-content-key makes ingestion **idempotent** (safe re-runs).
- **Quality gates:** JSON-schema validation, language detection, dead-link checks, **spam/bot heuristics** (account age, duplication rate), and the **relevance filter** (brand match + semantic finance gate) before anything is classified. **PII is masked** before any text leaves the box (as in the cascade service).
- **Drift monitoring:** track classification-confidence distribution and sentiment mix over time; a sudden drop in confidence flags model/data drift for review.

## 4. Scalability considerations
- **Decouple ingestion from processing** via a queue (Kafka/SQS) so collectors and GPU classification workers scale independently and a slow source never blocks the rest.
- **Cost-efficient classification cascade** (the core idea from Part 1): the cheap local model handles the confident ~80–90 % of traffic; only low-confidence/ambiguous records hit the LLM. This bounds cost as volume grows. Add **batched LLM calls** and **prompt caching** for the escalated set.
- **Horizontal scaling** of collectors and classifiers (containers + autoscaling); per-source **rate-limit handling with exponential backoff**; result caching for repeated content.
- **Incremental processing:** only new/changed records are processed each cycle; dedup runs against a bounded recent window, not the full history.

## 5. Key limitations & trade-offs
- **X/Twitter access & cost** is the hardest constraint — the official API is expensive and rate-limited, pushing toward paid third-party providers (cost vs coverage trade-off).
- **Scraping is fragile and ToS-sensitive** — site changes and anti-bot measures require maintenance; prefer official feeds/APIs and respect robots.txt / legal limits.
- **LLM cost vs accuracy** — the cascade mitigates this, but a higher escalation rate (more accuracy) costs more; the confidence threshold is the tuning knob.
- **Reach / impression data** isn't uniformly available across sources, so impact-weighted metrics remain approximate.
- **Real-time vs batch** — near-real-time ingestion (X stream) raises infra cost and complexity; daily batch is cheaper and sufficient for most reputation reporting. Start batch, add streaming only where latency matters.
