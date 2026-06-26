"""
Stage 6 — Intelligence & metrics.

Rolls the per-record classifications up into the executive metrics a reputation
consultant uses: Net Sentiment, Share of Voice vs competitors, a composite
Reputation Health Score (0-100), top themes, and a ranked risk queue.

Formulas follow the standard reputation-index model (SoV / Net-Sentiment /
Media-Quality / Risk), adapted to the signals available in this dataset.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from . import config as C

_TIER_WEIGHT = {
    "Tier-1 News": 1.0, "Review": 0.7, "Tier-2 / Aggregator": 0.6,
    "Social": 0.5, "Other / Unknown": 0.4,
}
_SALIENCE_WEIGHT = {"headline": 1.0, "body": 0.7, "first_party": 0.7, "peripheral": 0.4,
                    "topical": 0.4}  # 'topical' kept for backward-compat


def _dist(s: pd.Series) -> dict:
    vc = s.value_counts()
    pct = (vc / vc.sum() * 100).round(1)
    return {str(k): {"count": int(vc[k]), "pct": float(pct[k])} for k in vc.index}


def _net_sentiment(s: pd.Series) -> float:
    n = len(s)
    if n == 0:
        return 0.0
    pos = (s == "Positive").sum()
    neg = (s == "Negative").sum()
    return round((pos - neg) / n, 3)


def share_of_voice(df: pd.DataFrame) -> dict:
    """Brand vs competitors, by number of mentioning records across the corpus."""
    brand = int(df["has_brand"].sum()) if "has_brand" in df else len(df)
    comp_counts: dict[str, int] = {}
    for lst in df["competitors_mentioned"]:
        for c in lst:
            comp_counts[c] = comp_counts.get(c, 0) + 1
    total = brand + sum(comp_counts.values())
    sov = round(100 * brand / total, 1) if total else 100.0
    return {
        "brand": C.BRAND,
        "brand_mentions": brand,
        "share_of_voice_pct": sov,
        "competitor_mentions": dict(sorted(comp_counts.items(), key=lambda kv: -kv[1])),
    }


def reputation_health_score(df: pd.DataFrame) -> dict:
    """Composite 0-100 index with transparent, documented components."""
    sent = df["sentiment"]
    n = len(df)

    # 1. Net sentiment, reach-weighted -> 0-100
    w = df["reach"].fillna(df["reach"].median() if df["reach"].notna().any() else 1)
    w = w.clip(lower=1)
    pol = df["sentiment_polarity"].fillna(0)
    net_w = float(np.average(pol, weights=w))           # [-1, 1]
    net_component = (net_w + 1) / 2 * 100

    # 2. Media quality = tier x prominence -> 0-100
    tw = df["source_tier"].map(_TIER_WEIGHT).fillna(0.4)
    sw = df["brand_salience"].map(_SALIENCE_WEIGHT).fillna(0.4) if "brand_salience" in df else 0.7
    media_component = float((tw * sw).mean()) * 100

    # 3. Positive share -> 0-100
    pos_component = float((sent == "Positive").mean()) * 100

    # 4. Risk penalty -> 0-100 (100 = no risk exposure)
    mean_risk = float(df["risk_score"].clip(0, 1.3).mean()) if "risk_score" in df else 0.0
    risk_component = max(0.0, 100 * (1 - mean_risk))

    comps = {
        "net_sentiment": round(net_component, 1),
        "media_quality": round(media_component, 1),
        "positive_share": round(pos_component, 1),
        "risk_penalty": round(risk_component, 1),
    }
    score = sum(comps[k] * C.REPUTATION_WEIGHTS[k] for k in comps)
    band = ("Strong" if score >= 70 else "Healthy" if score >= 55
            else "Watch" if score >= 45 else "At Risk")
    return {
        "score": round(score, 1), "band": band,
        "components": comps, "weights": C.REPUTATION_WEIGHTS,
    }


def theme_summary(df: pd.DataFrame) -> list[dict]:
    out = []
    labels = df.attrs.get("theme_labels", {})
    descs = df.attrs.get("theme_descriptions", {})
    for tid, grp in df.groupby("theme_id"):
        out.append({
            "theme_id": int(tid),
            "label": labels.get(tid, df.loc[grp.index[0], "theme"]),
            "description": descs.get(tid),
            "size": int(len(grp)),
            "net_sentiment": _net_sentiment(grp["sentiment"]),
            "dominant_driver": grp["driver"].mode().iat[0] if len(grp) else None,
            "top_sentiment": grp["sentiment"].mode().iat[0] if len(grp) else None,
        })
    return sorted(out, key=lambda d: -d["size"])


def top_keyphrase_themes(df: pd.DataFrame, top_n: int = 12) -> list[dict]:
    """Corpus-level 'top discussion themes' from keyphrase frequency.

    More robust than KMeans clusters on this small, homogeneous corpus: counts
    how often each keyphrase recurs and attaches its net sentiment.
    """
    from collections import Counter
    bucket: dict[str, list] = {}
    counts: Counter = Counter()
    for _, r in df.iterrows():
        kps = r["keyphrases"] if isinstance(r["keyphrases"], list) else []
        for kp in {k.lower().strip() for k in kps if len(k) > 3}:
            counts[kp] += 1
            bucket.setdefault(kp, []).append(r["sentiment"])
    out = []
    for kp, c in counts.most_common(top_n):
        out.append({
            "theme": kp,
            "mentions": int(c),
            "net_sentiment": _net_sentiment(pd.Series(bucket[kp])),
        })
    return out


def driver_breakdown(df: pd.DataFrame) -> list[dict]:
    rows = []
    for drv, grp in df.groupby("driver"):
        rows.append({
            "driver": drv,
            "mentions": int(len(grp)),
            "net_sentiment": _net_sentiment(grp["sentiment"]),
            "positive": int((grp["sentiment"] == "Positive").sum()),
            "neutral": int((grp["sentiment"] == "Neutral").sum()),
            "negative": int((grp["sentiment"] == "Negative").sum()),
            "avg_reach": int(grp["reach"].dropna().mean()) if grp["reach"].notna().any() else None,
        })
    return sorted(rows, key=lambda d: -d["mentions"])


def risk_queue(df: pd.DataFrame, top_n: int = 12) -> list[dict]:
    rq = df[df["risk_flag"]].sort_values("risk_score", ascending=False).head(top_n)
    cols = ["record_id", "date", "source", "source_tier", "driver", "sub_driver",
            "sentiment", "risk_score", "reach", "url"]
    out = []
    for _, r in rq[cols].iterrows():
        d = r.to_dict()
        d["date"] = None if pd.isna(d["date"]) else str(pd.to_datetime(d["date"]).date())
        d["reach"] = None if pd.isna(d["reach"]) else int(d["reach"])
        d["snippet"] = df.loc[df["record_id"] == r["record_id"], "text"].iat[0][:200]
        out.append(d)
    return out


def temporal(df: pd.DataFrame) -> list[dict]:
    d = df.dropna(subset=["date"]).copy()
    if d.empty:
        return []
    g = d.set_index("date").resample("ME")
    out = []
    for period, grp in g:
        if len(grp) == 0:
            continue
        out.append({
            "month": str(period.date())[:7],
            "mentions": int(len(grp)),
            "net_sentiment": _net_sentiment(grp["sentiment"]),
        })
    return out


def sentiment_validation(df: pd.DataFrame) -> dict:
    """Agreement between our FinBERT sentiment and the provided labels (QA)."""
    m = df.dropna(subset=["sentiment_provided"])
    if m.empty:
        return {}
    agree = (m["sentiment"] == m["sentiment_provided"]).mean()
    confmat = (
        pd.crosstab(m["sentiment_provided"], m["sentiment"])
        .reindex(index=["Positive", "Neutral", "Negative"],
                 columns=["Positive", "Neutral", "Negative"], fill_value=0)
    )
    return {
        "n_compared": int(len(m)),
        "agreement_pct": round(float(agree) * 100, 1),
        "confusion_matrix": confmat.to_dict(),
    }


def _macro_f1(y_true, y_pred, labels) -> float:
    f1s = []
    for lab in labels:
        tp = int(((y_true == lab) & (y_pred == lab)).sum())
        fp = int(((y_true != lab) & (y_pred == lab)).sum())
        fn = int(((y_true == lab) & (y_pred != lab)).sum())
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * p * r / (p + r) if p + r else 0.0)
    return round(sum(f1s) / len(f1s), 3) if f1s else 0.0


def classification_validation(df: pd.DataFrame) -> dict:
    """Accuracy of the cheap zero-shot classifier against the Claude silver-gold
    reference — the missing 'how do I know it's right?' evidence."""
    if "claude_driver" not in df.columns:
        return {}
    m = df.dropna(subset=["claude_driver", "claude_sub_driver"])
    if m.empty:
        return {}
    out = {
        "reference": "Claude Sonnet 4.6 (independent silver-gold annotator, not human)",
        "n": int(len(m)),
        "driver_accuracy_zeroshot_pct": round((m["zeroshot_driver"] == m["claude_driver"]).mean() * 100, 1),
        "sub_driver_accuracy_zeroshot_pct": round((m["zeroshot_sub_driver"] == m["claude_sub_driver"]).mean() * 100, 1),
        "driver_macro_f1_zeroshot": _macro_f1(m["claude_driver"], m["zeroshot_driver"], C.DRIVERS),
        "sub_driver_macro_f1_zeroshot": _macro_f1(m["claude_sub_driver"], m["zeroshot_sub_driver"], C.SUBDRIVERS),
    }
    hc = m[~m["was_low_confidence"]]
    if len(hc):
        out["n_high_confidence"] = int(len(hc))
        out["driver_accuracy_high_conf_pct"] = round((hc["zeroshot_driver"] == hc["claude_driver"]).mean() * 100, 1)
        out["sub_driver_accuracy_high_conf_pct"] = round((hc["zeroshot_sub_driver"] == hc["claude_sub_driver"]).mean() * 100, 1)
    sm = df.dropna(subset=["sentiment_provided", "claude_sentiment"])
    if len(sm):
        out["sentiment_three_way_agreement_pct"] = {
            "provided_vs_ours": round((sm["sentiment"] == sm["sentiment_provided"]).mean() * 100, 1),
            "provided_vs_claude": round((sm["claude_sentiment"] == sm["sentiment_provided"]).mean() * 100, 1),
            "ours_vs_claude": round((sm["sentiment"] == sm["claude_sentiment"]).mean() * 100, 1),
        }
    return out


def _crosstab(df: pd.DataFrame, idx: str, col: str) -> dict:
    ct = pd.crosstab(df[idx], df[col])
    return {str(i): {str(c): int(ct.loc[i, c]) for c in ct.columns} for i in ct.index}


def sub_driver_breakdown(df: pd.DataFrame) -> list[dict]:
    rows = []
    for sub, grp in df.groupby("sub_driver"):
        rows.append({
            "sub_driver": sub, "driver": C.SUB_TO_DRIVER.get(sub),
            "mentions": int(len(grp)), "net_sentiment": _net_sentiment(grp["sentiment"]),
            "positive": int((grp["sentiment"] == "Positive").sum()),
            "negative": int((grp["sentiment"] == "Negative").sum()),
        })
    return sorted(rows, key=lambda d: -d["mentions"])


def top_mentions(df: pd.DataFrame, sentiment: str, n: int = 5) -> list[dict]:
    """Highest-reach quotable mentions of a given polarity — dashboard-ready."""
    sub = df[df["sentiment"] == sentiment].sort_values("reach", ascending=False, na_position="last")
    out = []
    for _, r in sub.head(n).iterrows():
        out.append({
            "record_id": int(r["record_id"]), "source": r["source"],
            "driver": r["driver"], "sub_driver": r["sub_driver"],
            "reach": None if pd.isna(r["reach"]) else int(r["reach"]),
            "date": None if pd.isna(r["date"]) else str(pd.to_datetime(r["date"]).date()),
            "snippet": str(r["text"])[:220], "url": r.get("url", ""),
        })
    return out


def spokesperson_sentiment(df: pd.DataFrame) -> list[dict]:
    bucket: dict[str, list] = {}
    for _, r in df.iterrows():
        for p in (r["people_mentioned"] if isinstance(r["people_mentioned"], list) else []):
            bucket.setdefault(p, []).append(r["sentiment"])
    out = [{"person": p, "mentions": len(s), "net_sentiment": _net_sentiment(pd.Series(s)),
            "positive": int(pd.Series(s).eq("Positive").sum()),
            "negative": int(pd.Series(s).eq("Negative").sum())}
           for p, s in bucket.items()]
    return sorted(out, key=lambda d: -d["mentions"])


def build_insights(df: pd.DataFrame, counts: dict) -> dict:
    return {
        "brand": C.BRAND,
        "counts": counts,
        "reputation_health_score": reputation_health_score(df),
        "share_of_voice": share_of_voice(df),
        "distributions": {
            "sentiment": _dist(df["sentiment"]),
            "driver": _dist(df["driver"]),
            "sub_driver": _dist(df["sub_driver"]),
            "channel": _dist(df["channel"]),
            "source_tier": _dist(df["source_tier"]),
            "emotion": _dist(df["emotion"]),
            "brand_salience": _dist(df["brand_salience"]) if "brand_salience" in df else {},
        },
        "net_sentiment_overall": _net_sentiment(df["sentiment"]),
        "driver_breakdown": driver_breakdown(df),
        "sub_driver_breakdown": sub_driver_breakdown(df),
        "driver_x_sentiment": _crosstab(df, "driver", "sentiment"),
        "channel_x_sentiment": _crosstab(df, "channel", "sentiment"),
        "themes": theme_summary(df),
        "top_discussion_themes": top_keyphrase_themes(df),
        "temporal": temporal(df),
        "people_mentioned": _people_freq(df),
        "spokesperson_sentiment": spokesperson_sentiment(df),
        "top_positive_mentions": top_mentions(df, "Positive"),
        "top_negative_mentions": top_mentions(df, "Negative"),
        "risk_queue": risk_queue(df),
        "sentiment_validation": sentiment_validation(df),
        "classification_validation": classification_validation(df),
        "low_confidence_records": int(df["low_confidence"].sum()),
    }


def _people_freq(df: pd.DataFrame) -> dict:
    freq: dict[str, int] = {}
    for lst in df["people_mentioned"]:
        for p in lst:
            freq[p] = freq.get(p, 0) + 1
    return dict(sorted(freq.items(), key=lambda kv: -kv[1]))
