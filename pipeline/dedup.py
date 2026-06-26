"""
Stage 2 — Deduplication.

EDA finding: the Play Store app URL repeats ~15x but every row is a *distinct*
review, so we must NOT dedup on URL. We dedup on normalized content, on
embedding near-duplicates, and on cross-source headline syndication.

PRIORITY: precision over recall — never collapse a genuinely distinct record.
Every collapse rule is conservative and corroborated, and review/social rows
(whose "titles" are category labels like "Digital Experience") are excluded from
the headline pass so distinct app reviews can never be merged.

When a duplicate group is found we keep the **highest-reach** copy as canonical
and **consolidate the dropped copies' reach** into it (so Share-of-Voice / impact
are not understated), recording `dup_count`. Dropped rows are returned for audit.
"""
from __future__ import annotations
import re
import numpy as np
import pandas as pd

_NORM_RE = re.compile(r"[^a-z0-9 ]+")
# "Titles" that are really category labels (app-review rows) — never syndication keys.
_CATEGORY_TITLES = ("digital experience", "customer support", "product service quality",
                    "product and service quality")


def _norm(text: str) -> str:
    return _NORM_RE.sub(" ", str(text).lower()).strip()


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.parent[max(ra, rb)] = min(ra, rb)  # deterministic
        return True


def dedup(
    df: pd.DataFrame,
    embedder=None,
    sim_threshold: float = 0.95,        # conservative near-dup cutoff (precision-first)
    title_body_min: float = 0.55,       # body corroboration for headline syndication
):
    """Returns (kept_df, removed_df)."""
    df = df.copy().reset_index(drop=True)
    n = len(df)
    ids = df["record_id"].tolist()
    norm = df["text"].map(_norm).tolist()
    title_norm = df["_Title"].map(_norm).tolist() if "_Title" in df else [""] * n
    channel = df["channel"].tolist() if "channel" in df else [""] * n
    source = df["source"].tolist() if "source" in df else [""] * n
    reach = pd.to_numeric(df.get("reach", pd.Series([np.nan] * n)), errors="coerce")

    uf = _UnionFind(n)
    reason: list[str | None] = [None] * n

    def set_reason(node: int, r: str) -> None:
        if reason[node] is None:
            reason[node] = r

    # shared embeddings (used by both the near-dup and the corroboration check)
    sims = None
    if embedder is not None and n > 1:
        emb = embedder.encode(df["text"].tolist(), normalize_embeddings=True,
                              show_progress_bar=False)
        sims = emb @ emb.T

    # ---- 1. exact normalized-content duplicates -----------------------------
    seen: dict[str, int] = {}
    for i in range(n):
        if not norm[i]:
            continue
        if norm[i] in seen:
            uf.union(seen[norm[i]], i)
            set_reason(i, "exact_content")
        else:
            seen[norm[i]] = i

    # ---- 2. embedding near-duplicates (re-worded reposts) -------------------
    if sims is not None:
        for i in range(n):
            for j in range(i + 1, n):
                if sims[i, j] >= sim_threshold:
                    uf.union(i, j)
                    set_reason(i, f"near_dup({sims[i, j]:.2f})")
                    set_reason(j, f"near_dup({sims[i, j]:.2f})")

    # ---- 3. cross-source headline syndication (strict, precision-first) ------
    # Only News/Web rows with a substantive, non-category headline. A group is
    # collapsed only when the SAME headline appears across DIFFERENT sources AND
    # the bodies are at least loosely similar — so a coincidental shared headline
    # on genuinely different articles is not merged.
    title_groups: dict[str, list[int]] = {}
    for i in range(n):
        t = title_norm[i]
        if channel[i] != "News / Web" or len(t) < 25:
            continue
        if any(c in t for c in _CATEGORY_TITLES):
            continue
        title_groups.setdefault(t, []).append(i)

    for members in title_groups.values():
        if len(members) < 2:
            continue
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                i, j = members[a], members[b]
                if source[i] == source[j]:                 # same outlet -> keep both
                    continue
                if sims is not None and sims[i, j] < title_body_min:
                    continue                                # bodies too different -> keep both
                uf.union(i, j)
                set_reason(i, "title_syndication")
                set_reason(j, "title_syndication")

    # ---- resolve components: canonical = max reach, consolidate reach --------
    comps: dict[int, list[int]] = {}
    for i in range(n):
        comps.setdefault(uf.find(i), []).append(i)

    dup_of: list[object] = [pd.NA] * n
    dup_reason: list[object] = [pd.NA] * n
    dup_count = [1] * n
    new_reach = reach.copy()

    for members in comps.values():
        if len(members) == 1:
            continue
        # highest reach wins (NaN ranks lowest); tie -> lowest record_id
        canonical = max(members, key=lambda i: (reach.iloc[i] if pd.notna(reach.iloc[i]) else -1.0,
                                                -ids[i]))
        grp_reach = reach.iloc[members].dropna()
        if len(grp_reach):
            new_reach.iloc[canonical] = float(grp_reach.sum())
        dup_count[canonical] = len(members)
        for i in members:
            if i == canonical:
                continue
            dup_of[i] = ids[canonical]
            dup_reason[i] = reason[i] or "duplicate"

    df["reach"] = new_reach.values
    df["dup_count"] = dup_count
    df["_dup_of"] = dup_of
    df["_dup_reason"] = dup_reason

    kept = df[df["_dup_of"].isna()].drop(columns=["_dup_of", "_dup_reason"]).copy()
    removed = (df[df["_dup_of"].notna()]
               .rename(columns={"_dup_of": "dup_of", "_dup_reason": "dup_reason"})
               .copy())
    return kept, removed
