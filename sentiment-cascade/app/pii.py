"""
PII masking — runs before ANY model call (local or remote), so raw PII never
leaves the box and is never written to logs.

Structured PII is caught with regex; names optionally via an NER pass (skipped
gracefully if spaCy is unavailable). Masking is deterministic: the same input
always produces the same masked text and mask map.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Order matters — more specific / structured patterns first so a card number is
# not partially eaten by the generic phone/account matchers.
# More-specific patterns first. CARD (13-19 digits) must precede AADHAAR
# (exactly 12) so a 16-digit card isn't half-eaten by the 12-digit matcher;
# PHONE precedes the generic ACCOUNT matcher.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("PAN", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),                    # Indian PAN
    ("IFSC", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")),                    # bank IFSC
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),                      # 13-19 digit card
    ("AADHAAR", re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")),                  # spaced 12-digit Aadhaar
    ("PHONE", re.compile(r"(?:\+?91[-\s]?)?\b[6-9]\d{9}\b")),             # Indian mobile
    ("ACCOUNT", re.compile(r"\b\d{9,18}\b")),                             # generic acct no.
]


@dataclass
class MaskEntry:
    placeholder: str   # e.g. "[CARD_1]"
    original: str
    pii_type: str
    start: int         # position in the ORIGINAL string


def _ner_names(text: str) -> list[tuple[int, int, str]]:
    """Optional NER for person names. Returns (start, end, surface) spans.
    Silently returns [] if spaCy / a model is unavailable."""
    try:
        import spacy  # type: ignore

        nlp = _load_spacy()
        if nlp is None:
            return []
        doc = nlp(text)
        return [(e.start_char, e.end_char, e.text) for e in doc.ents if e.label_ == "PERSON"]
    except Exception:
        return []


_SPACY = None


def _load_spacy():
    global _SPACY
    if _SPACY is None:
        try:
            import spacy  # type: ignore

            _SPACY = spacy.load("en_core_web_sm")
        except Exception:
            _SPACY = False  # mark "tried and unavailable"
    return _SPACY or None


def mask(text: str) -> tuple[str, list[MaskEntry]]:
    """Return (masked_text, mask_map). Deterministic for a given input."""
    # 1. Collect candidate spans from structured patterns (priority order).
    spans: list[tuple[int, int, str, str]] = []  # (start, end, type, surface)
    occupied: list[tuple[int, int]] = []

    def _overlaps(s: int, e: int) -> bool:
        return any(not (e <= os or s >= oe) for os, oe in occupied)

    for pii_type, pat in _PATTERNS:
        for m in pat.finditer(text):
            s, e = m.start(), m.end()
            if _overlaps(s, e):
                continue
            spans.append((s, e, pii_type, m.group()))
            occupied.append((s, e))

    # 2. Optional names (lowest priority — only on still-free spans).
    for s, e, surface in _ner_names(text):
        if not _overlaps(s, e):
            spans.append((s, e, "NAME", surface))
            occupied.append((s, e))

    # 3. Deterministic numbering: per-type counter assigned in document order.
    spans.sort(key=lambda x: x[0])
    counters: dict[str, int] = {}
    entries: list[MaskEntry] = []
    for s, _e, pii_type, surface in spans:
        counters[pii_type] = counters.get(pii_type, 0) + 1
        placeholder = f"[{pii_type}_{counters[pii_type]}]"
        entries.append(MaskEntry(placeholder, surface, pii_type, s))

    # 4. Rebuild the string, replacing right-to-left so offsets stay valid.
    masked = text
    for entry in sorted(entries, key=lambda x: x.start, reverse=True):
        end = entry.start + len(entry.original)
        masked = masked[: entry.start] + entry.placeholder + masked[end:]

    return masked, entries
