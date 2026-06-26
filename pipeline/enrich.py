"""
Stage 5 — Enrichment ("above & beyond" signal extraction).

Adds intelligence that a consultant actually wants, beyond the required labels:
  - entity extraction: key people/spokespeople + competitor brands named
  - share-of-voice inputs: which competitors co-occur
  - keyphrase extraction (KeyBERT over local MiniLM embeddings)
  - semantic theme discovery (embed -> KMeans -> c-TF-IDF labels)
  - risk flagging for the consultant's attention queue
"""
from __future__ import annotations
import re
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS
from sklearn.metrics import silhouette_score
from . import config as C


# --------------------------------------------------------------------------- #
# Entities & competitors (gazetteer — more reliable than generic NER here)
# --------------------------------------------------------------------------- #
def extract_entities(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    def people(t):
        found = [p for p in C.KEY_PEOPLE if p.lower() in t]
        # de-dup short aliases when full name present
        if any("naren" in f.lower() for f in found):
            found = [f for f in found if f.lower() not in ("naren",)] or ["Sankaran Naren"]
        return sorted(set(found))

    def competitors(t):
        hits = []
        for brand, aliases in C.COMPETITORS.items():
            if any(a in t for a in aliases):
                hits.append(brand)
        return sorted(set(hits))

    df["people_mentioned"] = df["text_lc"].map(people)
    df["competitors_mentioned"] = df["text_lc"].map(competitors)
    df["is_competitive_context"] = df["competitors_mentioned"].map(len) > 0
    return df


# --------------------------------------------------------------------------- #
# Keyphrases
# --------------------------------------------------------------------------- #
def extract_keyphrases(df: pd.DataFrame, embedder) -> pd.DataFrame:
    df = df.copy()
    def _is_clean(phrase: str) -> bool:
        toks = set(phrase.lower().split())
        if toks & C.THEME_BRAND_TOKENS:          # any brand/person token -> drop
            return False
        return bool(toks - C.THEME_GENERIC_TOKENS)  # must have >=1 real topic word

    try:
        from keybert import KeyBERT
        kb = KeyBERT(model=embedder)
        phrases = []
        for t in df["text"].tolist():
            if len(t.split()) < 4:
                phrases.append([])
                continue
            kws = kb.extract_keywords(
                t, keyphrase_ngram_range=(1, 3), stop_words="english",
                use_mmr=True, diversity=0.6, top_n=8,
            )
            kept = [k for k, _ in kws if _is_clean(k)][:5]
            phrases.append(kept)
        df["keyphrases"] = phrases
    except Exception as e:  # graceful fallback
        df["keyphrases"] = [[] for _ in range(len(df))]
        print(f"[enrich] keyphrase extraction skipped: {e}")
    return df


# --------------------------------------------------------------------------- #
# Semantic theme discovery
# --------------------------------------------------------------------------- #
_THEME_STOP = set(ENGLISH_STOP_WORDS) | {
    "icici", "prudential", "mutual", "fund", "funds", "amc", "mf", "said",
    "says", "year", "years", "rs", "crore", "lakh", "new", "india", "indian",
}


def discover_themes(df: pd.DataFrame, embedder, n_themes: int = C.N_THEMES) -> pd.DataFrame:
    df = df.copy().reset_index(drop=True)
    texts = df["text"].tolist()
    emb = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    n = len(df)
    k = min(n_themes, max(2, n // 5))
    # pick k by silhouette across a small range (robustness over a fixed guess)
    best_k, best_s, best_labels = k, -1, None
    for kk in range(max(2, k - 2), min(n - 1, k + 3) + 1):
        km = KMeans(n_clusters=kk, random_state=C.RANDOM_STATE, n_init=10)
        labels = km.fit_predict(emb)
        if len(set(labels)) < 2:
            continue
        s = silhouette_score(emb, labels)
        if s > best_s:
            best_k, best_s, best_labels = kk, s, labels
    if best_labels is None:
        best_labels = np.zeros(n, dtype=int)

    df["theme_id"] = best_labels

    # label each cluster with class-based TF-IDF top terms (c-TF-IDF style)
    cv = CountVectorizer(ngram_range=(1, 2), stop_words=list(_THEME_STOP), min_df=1)
    X = cv.fit_transform([re.sub(r"[^a-zA-Z ]", " ", t) for t in texts])
    vocab = np.array(cv.get_feature_names_out())
    theme_labels = {}
    for c in sorted(set(best_labels)):
        rows = np.where(best_labels == c)[0]
        freq = np.asarray(X[rows].sum(axis=0)).ravel()
        top = vocab[freq.argsort()[::-1][:4]]
        theme_labels[c] = ", ".join(top)
    df["theme"] = df["theme_id"].map(theme_labels)
    df.attrs["theme_labels"] = theme_labels
    df.attrs["theme_silhouette"] = round(float(best_s), 3)
    return df


# --------------------------------------------------------------------------- #
# Risk flagging — the consultant's attention queue
# --------------------------------------------------------------------------- #
_HIGH_RISK_SUBS = {
    "Regulatory Compliance & Ethical Governance",
    "Customer Support & Complaint Resolution",
    "Digital & Omnichannel Experience",
}


def flag_risk(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    reach = df["reach"].fillna(0)
    reach_norm = (reach / reach.max()).fillna(0) if reach.max() > 0 else reach * 0

    def severity(r):
        if r["sentiment"] != "Negative":
            return 0.0
        base = 1.0 if r["sub_driver"] in _HIGH_RISK_SUBS else 0.6
        if r["sub_driver"] == "Regulatory Compliance & Ethical Governance":
            base = 1.3  # governance issues are the highest-stakes
        return base

    df["risk_severity"] = df.apply(severity, axis=1)
    # priority = severity x (0.4 + 0.6*reach), so reach amplifies but never zeroes
    df["risk_score"] = (df["risk_severity"] * (0.4 + 0.6 * reach_norm)).round(3)
    df["risk_flag"] = df["risk_score"] > 0
    return df
