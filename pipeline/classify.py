"""
Stage 4 — Classification (the core of Part 1), fully local / offline.

  * Sentiment  -> ProsusAI/finbert            (finance-domain, 3-way)
  * Driver/Sub -> DeBERTa-v3 zero-shot NLI     (8 sub-drivers -> parent driver)
  * Emotion    -> emotion-english-distilroberta (7 emotions, richer affect)

Design choices that matter:
  - Sub-driver is ALWAYS populated (best guess); a separate `*_confidence` and a
    `low_confidence` flag carry the uncertainty (never blank — assignment asks
    for driver AND sub-driver on every relevant record).
  - Driver confidence = sum of its children's sub-driver probabilities (robust
    hierarchical aggregation rather than an independent 3-way pass).
  - When the top-2 sub-drivers are within TIE_MARGIN, channel/title hints break
    the tie (e.g. an app-review row leans to Digital Experience).
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
import torch
from . import config as C

warnings.filterwarnings("ignore")


def _build_pipeline(task, model, cfg, **extra):
    """Construct a transformers pipeline, portable across transformers versions
    (newer uses `dtype=`, older uses `torch_dtype=`) and tolerant of fp16 issues."""
    from transformers import pipeline
    base = dict(task=task, model=model, device=cfg.pipe_device, **extra)
    for dtype_kw in ("dtype", "torch_dtype"):
        try:
            return pipeline(**base, **{dtype_kw: cfg.dtype})
        except TypeError:
            continue
        except Exception:
            break
    # last resort: no dtype hint (defaults to fp32)
    return pipeline(**base)


class Classifier:
    def __init__(self, cfg):
        self.cfg = cfg
        self._hyps = [C.SUB_HYPOTHESIS[s] for s in C.SUBDRIVERS]
        self._hyp_to_sub = {C.SUB_HYPOTHESIS[s]: s for s in C.SUBDRIVERS}

        self.zs = _build_pipeline(
            "zero-shot-classification", C.MODEL_ZEROSHOT, cfg,
            hypothesis_template="This text is about {}.",
        )
        self.sent = _build_pipeline(
            "text-classification", C.MODEL_SENTIMENT, cfg,
            top_k=None, truncation=True, max_length=512,
        )
        self.sent_social = _build_pipeline(
            "text-classification", C.MODEL_SENTIMENT_SOCIAL, cfg,
            top_k=None, truncation=True, max_length=512,
        )
        self.emo = _build_pipeline(
            "text-classification", C.MODEL_EMOTION, cfg,
            top_k=None, truncation=True, max_length=512,
        )

    # ---------------------------------------------------------------- sentiment
    @staticmethod
    def _norm_scores(scores: list[dict]) -> dict:
        """Map any model's labels to {positive, neutral, negative}."""
        m = {}
        for x in scores:
            lab = x["label"].lower()
            if lab in ("label_2", "pos"):
                lab = "positive"
            elif lab in ("label_1", "neu"):
                lab = "neutral"
            elif lab in ("label_0", "neg"):
                lab = "negative"
            m[lab] = x["score"]
        return m

    def _sentiment(self, df: pd.DataFrame) -> pd.DataFrame:
        """Channel-aware: social/review text -> social model, news -> FinBERT."""
        texts = df["text"].tolist()
        is_social = df["channel"].isin(C.SOCIAL_SENTIMENT_CHANNELS).tolist()
        news_out = self.sent(texts, batch_size=self.cfg.cls_batch)
        social_out = self.sent_social(texts, batch_size=self.cfg.cls_batch)
        rows = []
        for scores_n, scores_s, social in zip(news_out, social_out, is_social):
            d = self._norm_scores(scores_s if social else scores_n)
            label = max(d, key=d.get).capitalize()
            rows.append({
                "sentiment": label,
                "sentiment_confidence": round(max(d.values()), 3),
                "sentiment_polarity": round(d.get("positive", 0) - d.get("negative", 0), 3),
                "sentiment_model": "social" if social else "finbert",
            })
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------ emotion
    def _emotion(self, texts: list[str]) -> pd.Series:
        out = self.emo(texts, batch_size=self.cfg.cls_batch)
        return pd.Series([max(s, key=lambda x: x["score"])["label"] for s in out])

    # ----------------------------------------------------------- driver/subdriver
    def _drivers(self, df: pd.DataFrame) -> pd.DataFrame:
        res = self.zs(
            df["text"].tolist(), candidate_labels=self._hyps,
            multi_label=False, batch_size=self.cfg.zs_batch,
        )
        if isinstance(res, dict):
            res = [res]
        rows = []
        for (_, row), r in zip(df.iterrows(), res):
            # probability per sub-driver
            prob = {self._hyp_to_sub[lab]: sc for lab, sc in zip(r["labels"], r["scores"])}
            ranked = sorted(prob.items(), key=lambda kv: kv[1], reverse=True)
            top_sub, top_p = ranked[0]
            second_sub, second_p = ranked[1]

            tie_note = ""
            exact_hint, soft_hint = _hint_subdriver(row)
            if exact_hint:
                # the Title field literally IS a category label (review rows the
                # data provider pre-tagged) -> trust it as a hard override.
                if exact_hint != top_sub:
                    tie_note = f"title_hint_override({top_sub})"
                top_sub, top_p = exact_hint, max(prob[exact_hint], top_p)
            elif soft_hint and top_p - second_p < C.TIE_MARGIN and soft_hint in (top_sub, second_sub):
                # close call -> let the channel prior break the tie
                if soft_hint != top_sub:
                    tie_note = f"channel_hint->{soft_hint}"
                top_sub, top_p = soft_hint, prob[soft_hint]

            # driver prob = sum of children probabilities
            dprob: dict[str, float] = {d: 0.0 for d in C.DRIVERS}
            for s, p in prob.items():
                dprob[C.SUB_TO_DRIVER[s]] += p
            driver = C.SUB_TO_DRIVER[top_sub]

            rows.append({
                "driver": driver,
                "driver_confidence": round(dprob[driver], 3),
                "sub_driver": top_sub,
                "sub_driver_confidence": round(float(top_p), 3),
                "sub_driver_runner_up": second_sub,
                "low_confidence": bool(top_p < C.LOW_CONF_THRESHOLD),
                "classification_note": tie_note,
            })
        return pd.DataFrame(rows, index=df.index)

    # --------------------------------------------------------------------- run
    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy().reset_index(drop=True)
        texts = df["text"].tolist()
        sent = self._sentiment(df)
        df["emotion"] = self._emotion(texts).values
        drv = self._drivers(df).reset_index(drop=True)
        return pd.concat([df, sent, drv], axis=1)


def _hint_subdriver(row) -> tuple[str | None, str | None]:
    """Return (exact_title_hint, soft_channel_hint).

    exact_title_hint: the Title field is (essentially) a category label.
    soft_channel_hint: a weak prior from the channel (tie-breaker only).
    """
    title_lc = str(row.get("_Title", "")).lower().strip()
    exact = None
    for k, v in C.TITLE_HINTS.items():
        # exact-ish: the title is the hint (allow trailing punctuation/short noise)
        if title_lc == k or title_lc.startswith(k) and len(title_lc) <= len(k) + 3:
            exact = v
            break
    priors = C.CHANNEL_PRIORS.get(row.get("channel", ""), [])
    soft = priors[0] if priors else None
    return exact, soft
