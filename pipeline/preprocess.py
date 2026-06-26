"""
Stage 1 — Cleaning, standardization & basic preprocessing.

Turns the raw, inconsistent spreadsheet into a tidy frame with:
  - standardized sentiment casing
  - a unified, cleaned text blob (Title + Opening Text + Hit Sentence)
  - parsed dates, derived channel, source tier, language, salience/prominence
No records are dropped here (dedup/relevance happen in later, auditable stages).
"""
from __future__ import annotations
import re
import html
import logging
import pandas as pd
from . import config as C

_log = logging.getLogger("preprocess")

_URL_RE = re.compile(r"https?://\S+")
_WS_RE = re.compile(r"\s+")
_CTRL_RE = re.compile(r"[​‌‍﻿]")  # zero-width junk
_TLD_SUFFIXES = (".com", ".in", ".net", ".org", ".co")


def _canon_source(s: str) -> str:
    """Light, identity-preserving outlet-name cleanup: strip a trailing TLD
    (Moneycontrol.com -> Moneycontrol). Never touches URL-style source ids like
    'reddit.com/r/mutualfunds' (distinct subreddits must stay distinct)."""
    s = s.strip()
    if "/" in s:
        return s
    low = s.lower()
    for suf in _TLD_SUFFIXES:
        if low.endswith(suf):
            return s[: -len(suf)]
    return s


def _clean_text(s: object) -> str:
    if pd.isna(s):
        return ""
    s = html.unescape(str(s))
    s = _CTRL_RE.sub("", s)
    s = _URL_RE.sub(" ", s)
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    s = _WS_RE.sub(" ", s).strip()
    return s


def _channel(source: str, url: str) -> str:
    s, u = source.lower(), url.lower()
    if "reddit" in s or "reddit" in u:
        return "Reddit"
    if "linkedin" in s or "linkedin" in u:
        return "LinkedIn"
    if any(k in u or k in s for k in C.REVIEW_SOURCES):
        return "App Store / Reviews"
    if "x.com" in u or "twitter" in u:
        return "X/Twitter"
    return "News / Web"


def _tier(source: str, url: str, channel: str) -> str:
    s, u = source.lower(), url.lower()
    blob = s + " " + u
    if channel == "App Store / Reviews":
        return "Review"
    if channel in ("Reddit", "LinkedIn", "X/Twitter"):
        return "Social"
    if any(k in blob for k in C.TIER1_NEWS):
        return "Tier-1 News"
    if any(k in blob for k in C.TIER2_AGG):
        return "Tier-2 / Aggregator"
    return "Other / Unknown"


def _detect_lang(text: str) -> str:
    if len(text) < 12:
        return "unknown"
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0
        return detect(text)
    except Exception:
        return "unknown"


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Return a standardized copy of the raw dataframe (no rows dropped)."""
    df = df.copy()
    df.insert(0, "record_id", range(1, len(df) + 1))

    # --- sentiment casing standardization (the provided, messy labels) -------
    _raw_sent = df["Sentiment"].astype(str).str.strip().str.lower()
    df["sentiment_provided"] = _raw_sent.map(
        {"positive": "Positive", "neutral": "Neutral", "negative": "Negative"}
    )
    # robustness guard: surface (don't silently drop) any value that didn't map
    _unmapped = df["Sentiment"].notna() & df["sentiment_provided"].isna()
    if _unmapped.any():
        bad = sorted(df.loc[_unmapped, "Sentiment"].astype(str).unique())
        _log.warning("standardize: %d provided-sentiment value(s) outside "
                     "{Positive,Neutral,Negative} -> left blank: %s",
                     int(_unmapped.sum()), bad)

    # --- clean individual text fields ----------------------------------------
    for col in ["Title", "Opening Text", "Hit Sentence"]:
        df[f"_{col}"] = df[col].map(_clean_text)

    # --- unified text blob (dedupe overlapping fragments) --------------------
    def _blob(r):
        parts, seen = [], set()
        for c in ["_Title", "_Opening Text", "_Hit Sentence"]:
            t = r[c]
            key = t.lower()
            if t and key not in seen:
                parts.append(t)
                seen.add(key)
        return " — ".join(parts)

    df["text"] = df.apply(_blob, axis=1)
    df["text_lc"] = df["text"].str.lower()
    df["word_count"] = df["text"].str.split().map(len)

    # --- metadata ------------------------------------------------------------
    df["source"] = df["Source Name"].fillna("Unknown").astype(str).map(_canon_source)
    df["url"] = df["URL"].fillna("").astype(str).str.strip()
    df["channel"] = df.apply(lambda r: _channel(r["source"], r["url"]), axis=1)
    df["source_tier"] = df.apply(
        lambda r: _tier(r["source"], r["url"], r["channel"]), axis=1
    )
    df["date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["language"] = df["text"].map(_detect_lang)

    # --- salience / prominence: is the brand named in the headline? ----------
    title_lc = df["_Title"].str.lower()
    df["brand_in_title"] = title_lc.apply(
        lambda t: any(b in t for b in C.BRAND_TERMS)
    )
    df["reach"] = pd.to_numeric(df["Reach"], errors="coerce")

    return df
