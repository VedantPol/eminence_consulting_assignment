#!/usr/bin/env python3
"""
Phase 1 orchestrator — Data Processing, Classification & Intelligence.

Runs the full, auditable pipeline end-to-end and writes the deliverables:

    Dataset.xlsx
        -> standardize   (sentiment casing, text blob, dates, channel/tier/language)
        -> dedup         (content + embedding + cross-source syndication; auditable)
        -> relevance     (two-tier filter; drops off-topic, tiers the rest)
        -> classify      (FinBERT/social sentiment + DeBERTa zero-shot driver/sub-driver)
        -> LLM escalate  (Claude Sonnet 4.6 re-classifies low-confidence rows; offline-safe)
        -> enrich        (entities, competitors, keyphrases, themes, reach-weighted risk)
        -> intelligence  (Net Sentiment, Share of Voice, Reputation Health Score, risk queue)

Outputs (in ./outputs):
    cleaned_classified.xlsx   the processed dataset (+ audit & insight sheets)
    classified.csv            flat table of the same
    insights.json             machine-readable metrics for the dashboard (Part 2)
    pipeline_report.md        human-readable run summary

Run:  ./run.sh        (recommended — sets up env + models)   or   python run_phase1.py
"""
from __future__ import annotations
import json
import time
import warnings
import pandas as pd

from pipeline import config as C
from pipeline import preprocess, dedup, relevance, enrich, intelligence
from pipeline import device as devmod
from pipeline.classify import Classifier

warnings.filterwarnings("ignore")


def log(stage, msg=""):
    print(f"[{time.strftime('%H:%M:%S')}]  {stage:<22} {msg}", flush=True)


def _classify_with_fallback(df, cfg, log):
    """Run classification on the detected device; on any GPU error, fall back to
    CPU so the pipeline completes on *any* system."""
    try:
        return Classifier(cfg).run(df)
    except Exception as e:
        if cfg.kind == "cpu":
            raise
        log("CLASSIFY", f"{cfg.kind} path failed ({type(e).__name__}: {e}) -> retrying on CPU")
        try:
            import torch, gc
            gc.collect()
            torch.cuda.empty_cache()
        except Exception:
            pass
        cpu_cfg = devmod.detect(force_cpu=True)
        return Classifier(cpu_cfg).run(df)


def _llm_stage(df, log):
    """Claude Sonnet 4.6 labels every row, serving two purposes in one pass:
      1. Silver-gold validation  — an independent reference for the zero-shot
         classifier, so we can report real driver/sub-driver accuracy (not just
         a confidence number).
      2. Escalation              — low-confidence zero-shot rows adopt Claude's
         label (the cheap classifier handles the confident majority).
    No-op when no API key is set, so the pipeline stays fully offline by default."""
    df = df.copy()
    df["classification_source"] = "zero_shot"
    # preserve the zero-shot labels so validation can compare them to Claude
    df["zeroshot_driver"] = df["driver"]
    df["zeroshot_sub_driver"] = df["sub_driver"]
    df["was_low_confidence"] = df["low_confidence"]
    for col in ("claude_driver", "claude_sub_driver", "claude_sentiment"):
        df[col] = pd.NA

    if not C.LLM_ENABLED:
        log("LLM STAGE", "skipped (no ANTHROPIC_API_KEY) — fully offline")
        return df

    from pipeline.llm_classify import ClaudeClassifier

    log("LLM STAGE", f"{C.LLM_MODEL} labelling all {len(df)} rows "
        f"(silver-gold validation + low-confidence escalation)")
    clf = ClaudeClassifier()
    results = clf.classify_many(df["text"].tolist())

    n_label = n_esc = 0
    for i, res in zip(df.index, results):
        if res is None:
            continue
        df.at[i, "claude_driver"] = res["driver"]
        df.at[i, "claude_sub_driver"] = res["sub_driver"]
        df.at[i, "claude_sentiment"] = res["sentiment"]
        n_label += 1
        # escalate ONLY the low-confidence rows (adopt Claude's driver/sub-driver;
        # sentiment keeps its own validated classifier — Claude over-calls positive
        # on neutral factual content; its opinion is kept in `sentiment_llm`).
        if df.at[i, "was_low_confidence"]:
            df.at[i, "driver"] = res["driver"]
            df.at[i, "sub_driver"] = res["sub_driver"]
            df.at[i, "sub_driver_confidence"] = res["confidence"]
            df.at[i, "low_confidence"] = res["confidence"] < C.LOW_CONF_THRESHOLD
            df.at[i, "sentiment_llm"] = res["sentiment"]
            df.at[i, "classification_source"] = "llm"
            df.at[i, "classification_note"] = (
                (str(df.at[i, "classification_note"] or "")) + " | llm_reclassified").strip(" |")
            n_esc += 1
    n_low = int(df["was_low_confidence"].sum())
    log("LLM STAGE", f"labelled {n_label}/{len(df)} | escalated {n_esc}/{n_low} low-confidence rows")
    return df


def _discover_themes(df, embedder, log):
    """Claude-named themes (presentation-ready) when a key is present; otherwise
    the local KMeans themer. Falls back to KMeans on any LLM error."""
    if C.LLM_ENABLED:
        try:
            from pipeline.themes_llm import ClaudeThemer
            return ClaudeThemer().assign(df, embedder)
        except Exception as e:
            log("THEMES", f"Claude themer failed ({e}); using local KMeans")
    return enrich.discover_themes(df, embedder)


def main():
    t0 = time.time()
    cfg = devmod.detect()
    log("DEVICE", f"{cfg.kind.upper()} :: {cfg.name} | dtype={str(cfg.dtype).split('.')[-1]} | "
        f"threads={cfg.threads} | batches(zs/cls/embed)={cfg.zs_batch}/{cfg.cls_batch}/{cfg.embed_batch}")

    log("LOAD", C.DATA_XLSX.name)
    raw = pd.read_excel(C.DATA_XLSX, sheet_name=0)
    n_raw = len(raw)

    # ---- embedder (shared by dedup / relevance / keyphrases / themes) --------
    log("MODELS", f"loading sentence embedder (MiniLM) on {cfg.kind}")
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer(C.MODEL_EMBED, device=cfg.st_device)

    # ---- Stage 1: standardize -----------------------------------------------
    df = preprocess.standardize(raw)
    log("STANDARDIZE", f"{len(df)} rows, sentiment casing fixed, text blob built")

    # ---- Stage 2: dedup ------------------------------------------------------
    df, removed_dups = dedup.dedup(df, embedder=embedder)
    log("DEDUP", f"removed {len(removed_dups)} duplicates -> {len(df)} unique")

    # ---- Stage 3: relevance --------------------------------------------------
    df, removed_irrel = relevance.filter_relevant(df, embedder=embedder)
    log("RELEVANCE", f"removed {len(removed_irrel)} irrelevant -> {len(df)} relevant")

    # ---- Stage 4: classify (the core) ---------------------------------------
    log("CLASSIFY", f"FinBERT + social + DeBERTa zero-shot + emotion on {cfg.kind}")
    df = _classify_with_fallback(df, cfg, log)
    log("CLASSIFY", "driver / sub-driver / sentiment / emotion assigned")

    # ---- Stage 4b: LLM labelling (silver-gold validation + escalation) -------
    df = _llm_stage(df, log)

    # ---- Stage 5: enrich -----------------------------------------------------
    df = enrich.extract_entities(df)
    df = enrich.extract_keyphrases(df, embedder)
    df = _discover_themes(df, embedder, log)        # Claude-named if key present
    df = enrich.flag_risk(df)
    log("ENRICH", f"themes={len(set(df['theme_id']))} "
        f"(method={df.attrs.get('theme_method','kmeans')}), "
        f"risk_flagged={int(df['risk_flag'].sum())}")

    # ---- Stage 6: intelligence ----------------------------------------------
    counts = {
        "raw": n_raw,
        "after_dedup": int(n_raw - len(removed_dups)),
        "duplicates_removed": int(len(removed_dups)),
        "irrelevant_removed": int(len(removed_irrel)),
        "final_relevant": int(len(df)),
    }
    insights = intelligence.build_insights(df, counts)
    rhs = insights["reputation_health_score"]
    log("INTELLIGENCE", f"Reputation Health Score = {rhs['score']} ({rhs['band']}) | "
        f"SoV = {insights['share_of_voice']['share_of_voice_pct']}%")

    # ---- Export --------------------------------------------------------------
    _export(df, removed_dups, removed_irrel, insights)
    log("DONE", f"in {time.time() - t0:.0f}s  ->  {C.OUTPUT_DIR}")
    _print_summary(insights, counts)


# --------------------------------------------------------------------------- #
def _export(df, removed_dups, removed_irrel, insights):
    out = C.OUTPUT_DIR

    # tidy column order for the human-facing dataset
    list_cols = ["people_mentioned", "competitors_mentioned", "keyphrases"]
    export = df.copy()
    for c in list_cols:
        export[c] = export[c].map(lambda x: ", ".join(x) if isinstance(x, list) else "")

    main_cols = [
        "record_id", "date", "source", "source_tier", "channel", "url",
        "Title", "text", "language", "word_count", "brand_salience", "relevance_score",
        "driver", "driver_confidence", "sub_driver", "sub_driver_confidence",
        "sub_driver_runner_up", "low_confidence", "classification_source", "classification_note",
        "zeroshot_driver", "zeroshot_sub_driver",
        "claude_driver", "claude_sub_driver", "claude_sentiment",
        "sentiment", "sentiment_confidence", "sentiment_polarity", "sentiment_model",
        "sentiment_llm", "sentiment_provided",
        "emotion", "theme_id", "theme", "keyphrases",
        "people_mentioned", "competitors_mentioned", "is_competitive_context",
        "reach", "dup_count", "risk_flag", "risk_score",
    ]
    main_cols = [c for c in main_cols if c in export.columns]

    with pd.ExcelWriter(out / "cleaned_classified.xlsx", engine="openpyxl") as xl:
        export[main_cols].to_excel(xl, sheet_name="classified", index=False)
        pd.DataFrame(insights["driver_breakdown"]).to_excel(
            xl, sheet_name="driver_breakdown", index=False)
        pd.DataFrame(insights["sub_driver_breakdown"]).to_excel(
            xl, sheet_name="sub_driver_breakdown", index=False)
        pd.DataFrame(insights["themes"]).to_excel(xl, sheet_name="themes", index=False)
        pd.DataFrame(insights["top_positive_mentions"] + insights["top_negative_mentions"]).to_excel(
            xl, sheet_name="top_mentions", index=False)
        if insights["spokesperson_sentiment"]:
            pd.DataFrame(insights["spokesperson_sentiment"]).to_excel(
                xl, sheet_name="spokesperson_sentiment", index=False)
        pd.DataFrame(insights["risk_queue"]).to_excel(xl, sheet_name="risk_queue", index=False)
        removed_dups_cols = [c for c in ["record_id", "source", "url", "text",
                             "dup_of", "dup_reason"] if c in removed_dups.columns]
        removed_dups[removed_dups_cols].to_excel(xl, sheet_name="removed_duplicates", index=False)
        irr_cols = [c for c in ["record_id", "source", "url", "text",
                    "relevance_score", "drop_reason"] if c in removed_irrel.columns]
        removed_irrel[irr_cols].to_excel(xl, sheet_name="removed_irrelevant", index=False)

    with open(out / "insights.json", "w") as f:
        json.dump(insights, f, indent=2, default=str)

    # flat CSV (universal) + parquet for fast dashboard loading when available
    export[main_cols].to_csv(out / "classified.csv", index=False)
    try:
        export[main_cols].to_parquet(out / "classified.parquet", index=False)
    except Exception:
        pass

    # compact per-record JSON for the dashboard's Content Explorer
    explorer_cols = [c for c in [
        "record_id", "date", "source", "source_tier", "channel", "url", "Title", "text",
        "driver", "sub_driver", "sentiment", "sentiment_confidence", "emotion", "theme",
        "brand_salience", "reach", "risk_flag", "classification_source",
        "people_mentioned", "competitors_mentioned", "keyphrases",
    ] if c in export.columns]
    export[explorer_cols].to_json(out / "classified.json", orient="records", date_format="iso")

    _write_report(insights)


def _write_report(insights):
    rhs = insights["reputation_health_score"]
    c = insights["counts"]
    lines = [
        f"# Phase 1 Pipeline Report — {insights['brand']}", "",
        f"**Reputation Health Score: {rhs['score']}/100 ({rhs['band']})**  ",
        f"Components: " + ", ".join(f"{k} {v}" for k, v in rhs["components"].items()),
        "",
        "## Funnel",
        f"- Raw records: {c['raw']}",
        f"- Duplicates removed: {c['duplicates_removed']}",
        f"- Irrelevant removed: {c['irrelevant_removed']}",
        f"- **Final relevant & classified: {c['final_relevant']}**",
        "",
        f"## Share of Voice: {insights['share_of_voice']['share_of_voice_pct']}% "
        f"(vs {len(insights['share_of_voice']['competitor_mentions'])} competitors named)",
        "",
        "## Driver breakdown",
    ]
    for d in insights["driver_breakdown"]:
        lines.append(f"- **{d['driver']}** — {d['mentions']} mentions, "
                     f"net sentiment {d['net_sentiment']:+.2f} "
                     f"(+{d['positive']}/{d['neutral']}/-{d['negative']})")
    lines += ["", "## Top themes"]
    for t in insights["themes"][:7]:
        lines.append(f"- *{t['label']}* — {t['size']} mentions, "
                     f"net sentiment {t['net_sentiment']:+.2f}")
    cv = insights.get("classification_validation") or {}
    if cv:
        lines += ["", "## Classification accuracy (zero-shot vs Claude silver-gold)",
                  f"- Reference: {cv['reference']} (n={cv['n']})",
                  f"- Driver: {cv['driver_accuracy_zeroshot_pct']}% acc, "
                  f"macro-F1 {cv['driver_macro_f1_zeroshot']}",
                  f"- Sub-driver: {cv['sub_driver_accuracy_zeroshot_pct']}% acc, "
                  f"macro-F1 {cv['sub_driver_macro_f1_zeroshot']}"]
        if "driver_accuracy_high_conf_pct" in cv:
            lines.append(f"- On the {cv['n_high_confidence']} high-confidence (non-escalated) rows: "
                         f"driver {cv['driver_accuracy_high_conf_pct']}%, "
                         f"sub-driver {cv['sub_driver_accuracy_high_conf_pct']}%")
        sw = cv.get("sentiment_three_way_agreement_pct", {})
        if sw:
            lines.append(f"- Sentiment 3-way: provided↔ours {sw['provided_vs_ours']}%, "
                         f"provided↔Claude {sw['provided_vs_claude']}%, "
                         f"ours↔Claude {sw['ours_vs_claude']}%")
    sv = insights["sentiment_validation"]
    if sv:
        lines += ["", f"## Sentiment QA vs provided labels: "
                  f"{sv['agreement_pct']}% agreement (n={sv['n_compared']})"]
    lines += ["", f"## Risk queue: {len(insights['risk_queue'])} flagged items "
              f"(top priority surfaced in outputs)"]
    (C.OUTPUT_DIR / "pipeline_report.md").write_text("\n".join(lines))


def _print_summary(insights, counts):
    rhs = insights["reputation_health_score"]
    print("\n" + "=" * 64)
    print(f"  REPUTATION HEALTH SCORE : {rhs['score']}/100  ({rhs['band']})")
    print(f"  Funnel                  : {counts['raw']} raw -> "
          f"{counts['final_relevant']} classified")
    print(f"  Share of Voice          : {insights['share_of_voice']['share_of_voice_pct']}%")
    print(f"  Overall net sentiment   : {insights['net_sentiment_overall']:+.2f}")
    print(f"  Risk items flagged      : {len(insights['risk_queue'])}")
    sv = insights["sentiment_validation"]
    if sv:
        print(f"  Sentiment QA agreement  : {sv['agreement_pct']}% (n={sv['n_compared']})")
    cv = insights.get("classification_validation") or {}
    if cv:
        print(f"  Driver acc (vs Claude)  : {cv['driver_accuracy_zeroshot_pct']}%  "
              f"(F1 {cv['driver_macro_f1_zeroshot']})")
        print(f"  Sub-driver acc          : {cv['sub_driver_accuracy_zeroshot_pct']}%  "
              f"(F1 {cv['sub_driver_macro_f1_zeroshot']})")
    print("=" * 64)


if __name__ == "__main__":
    main()
