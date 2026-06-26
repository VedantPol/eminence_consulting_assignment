"""
Stage 3 — Relevance filtering (two-tier).

EDA finding: ~37 rows don't name the brand. Not all are noise — app-store
reviews of the iPru app are highly relevant UX signal, while items like
"Best MBA Colleges in Kalyan" are pure noise. So:

  Tier 1 (rule):     keep if the brand/a key person is named OR it is a
                     first-party app/review row.
  Tier 2 (semantic): for the remainder, score topical relevance to the brand
                     via embedding similarity and a finance-domain gate; drop
                     off-topic rows.

Dropped rows are returned with a reason for an auditable trail.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from . import config as C

_FINANCE_TERMS = [
    "mutual fund", "amc", "sip", "nfo", "nav", "equity fund", "debt fund",
    "scheme", "portfolio", "expense ratio", "fund manager", "sebi", "investor",
    "hybrid fund", "index fund", "largecap", "midcap", "smallcap", "etf",
]
_BRAND_REFERENCE = (
    "ICICI Prudential Asset Management mutual funds, NFOs, SIPs, fund "
    "performance, the iPru mobile app, and company news"
)
SEM_THRESHOLD = 0.30  # cosine sim to the brand reference for borderline rows


def _has_any(text_lc: str, terms) -> bool:
    return any(t in text_lc for t in terms)


def filter_relevant(df: pd.DataFrame, embedder=None):
    """Returns (relevant_df, irrelevant_df) with a `drop_reason` on the latter."""
    df = df.copy()
    df["has_brand"] = df["text_lc"].apply(lambda t: _has_any(t, C.BRAND_TERMS))
    people_lc = [p.lower() for p in C.KEY_PEOPLE]
    df["has_person"] = df["text_lc"].apply(lambda t: _has_any(t, people_lc))
    df["is_review"] = df["channel"].eq("App Store / Reviews")
    df["has_finance"] = df["text_lc"].apply(lambda t: _has_any(t, _FINANCE_TERMS))

    # Semantic relevance score (recorded for every row, used only for borderline)
    if embedder is not None:
        ref = embedder.encode([_BRAND_REFERENCE], normalize_embeddings=True)
        docs = embedder.encode(
            df["text"].tolist(), normalize_embeddings=True, show_progress_bar=False
        )
        df["relevance_score"] = (docs @ ref.T).ravel().round(3)
    else:
        df["relevance_score"] = np.nan

    reasons = []
    for _, r in df.iterrows():
        if r["word_count"] == 0:
            reasons.append("no_text")
        elif r["has_brand"] or r["has_person"] or r["is_review"]:
            reasons.append(None)  # clearly relevant
        elif r["has_finance"] and (
            pd.isna(r["relevance_score"]) or r["relevance_score"] >= SEM_THRESHOLD
        ):
            # finance-adjacent and topically close, but brand not named:
            # keep but mark as low-salience for downstream weighting.
            reasons.append(None)
        else:
            reasons.append("off_topic_or_no_brand")
    df["drop_reason"] = reasons

    relevant = df[df["drop_reason"].isna()].drop(columns=["drop_reason"]).copy()
    irrelevant = df[df["drop_reason"].notna()].copy()

    # Brand-salience tier (relevance precision, no record dropped):
    #   headline    - brand named in the headline (primary subject)
    #   body        - brand named in the body (secondary subject)
    #   first_party - app-store / review row (genuine UX signal even w/o brand name)
    #   peripheral  - finance-topical but brand not the named subject (e.g. a generic
    #                 "best mutual funds" listicle) -> low weight in headline metrics
    def _salience(r) -> str:
        if r["brand_in_title"]:
            return "headline"
        if r["has_brand"] or r["has_person"]:
            return "body"
        if r["is_review"]:
            return "first_party"
        return "peripheral"

    relevant["brand_salience"] = relevant.apply(_salience, axis=1)
    return relevant, irrelevant
