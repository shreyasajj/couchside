"""Lyrics text helpers: romanize non-Latin scripts, tell whether a song is in English (Qt-free)."""

from __future__ import annotations

import re
from typing import Iterable

from anyascii import anyascii

# Gurmukhi / Devanagari nasal marks (bindi, tippi, anusvara, chandrabindu): anyascii writes
# "m"; spoken they are "n", or "m" before a labial (ਘੁੰਮੇ -> ghumme).
_NASALS = "ਂੰंँ"
_LABIALS = "ਪਫਬਭਮपफबभम"
_ADDAK = "ੱ"  # Gurmukhi: doubles the next consonant (ਗੱਲਾਂ -> gallan)
_GURMUKHI_VOWEL_SIGNS = set(chr(c) for c in range(0x0A3E, 0x0A4D))


def _needs_romanizing(ch: str) -> bool:
    """Non-Latin letters only: ASCII, accented Latin, punctuation, symbols stay."""
    o = ord(ch)
    if o < 0x0370 or 0x1E00 <= o <= 0x1EFF:        # Latin (+ extended / additional)
        return False
    if 0x2000 <= o <= 0x2BFF or o >= 0x1F000:       # punctuation, symbols, ♪, emoji
        return False
    return not ch.isspace()  # letters and their combining vowel signs / marks


def _prepare_indic(run: str) -> str:
    out: list[str] = []
    for i, ch in enumerate(run):
        nxt = run[i + 1] if i + 1 < len(run) else ""
        if ch in _NASALS:
            out.append("m" if nxt and nxt in _LABIALS else "n")
        elif ch == _ADDAK:
            prev = run[i - 1] if i > 0 else ""
            if prev and prev not in _GURMUKHI_VOWEL_SIGNS:
                out.append("a")  # the consonant before an addak keeps its inherent vowel
            if nxt:
                out.append(anyascii(nxt)[:1])  # double the next consonant's first letter
        else:
            out.append(ch)
    return "".join(out)


def romanize(text: str) -> str:
    """Write non-Latin runs (Gurmukhi, Devanagari, Cyrillic, Hangul, …) in English letters.

    Known limitation: Japanese kanji get Chinese readings (anyascii)."""
    if not text:
        return text
    out: list[str] = []
    run: list[str] = []
    for ch in text:
        if _needs_romanizing(ch):
            run.append(ch)
            continue
        if run:
            out.append(anyascii(_prepare_indic("".join(run))))
            run = []
        out.append(ch)
    if run:
        out.append(anyascii(_prepare_indic("".join(run))))
    return "".join(out)


_COMMON_EN = set("""
the and you i to a me my it in of is that your on be we all for this don't i'm with
can love just no so but what know like now oh when it's up down baby yeah be
are was will do not get got go let say one time never way see feel make
want need back night heart tonight never ever out come take give been there
they she he her him our us they're we're you're can't won't if from at as by
or how why who where then than too here have has had
""".split())
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?", re.UNICODE)


def is_english(lines: Iterable) -> bool:
    """Mostly Latin letters and enough common English words. Mixed songs (e.g. Punjabi
    with English phrases), other Latin-script languages and romanized text are not."""
    text = " ".join(getattr(line, "text", str(line)) for line in lines)
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    latin = sum(1 for c in letters if ord(c) < 0x0250)
    if latin / len(letters) < 0.9:
        return False
    words = [w.lower() for w in _WORD.findall(text)]
    if not words:
        return False
    return sum(1 for w in words if w in _COMMON_EN) / len(words) >= 0.12
