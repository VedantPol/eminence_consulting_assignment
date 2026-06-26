"""
Presentation-ready themes via Claude Sonnet 4.6.

KMeans on 95 short snippets gives a near-zero silhouette and fragmentary labels
("equity ex 100"). Instead we let Claude read the corpus and propose 6-8 named,
human-readable discussion themes, then assign every record to its closest theme
by embedding similarity (deterministic, no per-row API calls). The result is
dashboard-ready: clean theme names + size + net sentiment + dominant driver.

Falls back to the local KMeans themer (enrich.discover_themes) if unavailable.
"""
from __future__ import annotations

import logging

from . import config as C

log = logging.getLogger("themes_llm")

PROPOSE_TOOL = {
    "name": "propose_themes",
    "description": "Propose the main discussion themes covering the corpus.",
    "input_schema": {
        "type": "object",
        "properties": {
            "themes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Short title-case theme name (2-4 words)."},
                        "description": {"type": "string", "description": "One sentence describing the theme."},
                    },
                    "required": ["name", "description"],
                },
            }
        },
        "required": ["themes"],
    },
}

SYSTEM = (
    f"You are a media-intelligence analyst summarising coverage of {C.BRAND} "
    "(an Indian mutual-fund house). Identify the distinct discussion THEMES in "
    "the corpus — concrete topics a consultant would brief on (e.g. 'NFO & Fund "
    "Launches', 'Naren Market Outlook', 'App & Digital Experience', 'SIP Returns "
    "& Long-Term Performance', 'CSR & Financial Literacy', 'Regulatory & IPO'). "
    "Produce 6-8 mutually distinct, well-named themes that together cover the "
    "corpus. Return ONLY via the propose_themes tool."
)


class ClaudeThemer:
    def __init__(self):
        import anthropic

        self.model = C.LLM_MODEL
        self._client = anthropic.Anthropic(api_key=C.ANTHROPIC_API_KEY, max_retries=3, timeout=40)

    def propose(self, titles: list[str]) -> list[dict]:
        # compact corpus digest: unique, non-empty headlines/snippets
        digest = "\n".join(f"- {t[:140]}" for t in titles if t)
        resp = self._client.messages.create(
            model=self.model, max_tokens=700, temperature=0,
            thinking={"type": "disabled"},
            system=SYSTEM, tools=[PROPOSE_TOOL],
            tool_choice={"type": "tool", "name": "propose_themes"},
            messages=[{"role": "user", "content": f"Corpus ({len(titles)} mentions):\n{digest}"}],
        )
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "propose_themes":
                themes = block.input.get("themes", [])
                if themes:
                    return themes
        raise ValueError("no themes returned")

    def assign(self, df, embedder):
        """Adds theme_id / theme columns by embedding-similarity to theme texts."""
        import numpy as np

        df = df.copy().reset_index(drop=True)
        # propose themes from headlines (fall back to text snippets)
        titles = [t if isinstance(t, str) and t else s[:140]
                  for t, s in zip(df.get("_Title", df["text"]), df["text"])]
        themes = self.propose(titles)
        names = [t["name"] for t in themes]
        theme_text = [f"{t['name']}: {t['description']}" for t in themes]

        t_emb = embedder.encode(theme_text, normalize_embeddings=True, show_progress_bar=False)
        d_emb = embedder.encode(df["text"].tolist(), normalize_embeddings=True, show_progress_bar=False)
        sims = d_emb @ t_emb.T
        assign = sims.argmax(axis=1)
        df["theme_id"] = assign.astype(int)
        df["theme"] = [names[a] for a in assign]
        df.attrs["theme_labels"] = {i: n for i, n in enumerate(names)}
        df.attrs["theme_descriptions"] = {i: themes[i]["description"] for i in range(len(themes))}
        df.attrs["theme_silhouette"] = None  # llm-named, not silhouette-based
        df.attrs["theme_method"] = "claude_named"
        log.info("themes: %s", ", ".join(names))
        return df
