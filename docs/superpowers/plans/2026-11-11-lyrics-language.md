# Lyrics Language Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let the owner choose how lyrics read: **Romanized** (default: non-Latin scripts in English letters), **Original**, or **English only** (songs not sung mostly in English fall back to the artwork layout); plus an optional, off-by-default **English underneath** line-by-line translation from a choosable service (Google, DeepL, LibreTranslate). Lyrics size default stays Medium.

**Spec:** owner's decisions in conversation (2026-11-11): medium default; romanized default; original selectable; English-only selectable; translation underneath optional and off by default; translation service choosable among Google (no setup), DeepL (free API key), LibreTranslate (self-hosted address).

**Branch:** `lyrics-polish` (continues the parser, efficiency and size work).

## Verified (2026-11-11)

- `anyascii` romanizes Gurmukhi/Devanagari/Cyrillic/Hangul well; Gurmukhi tippi/bindi come out as "m" and addak as "'" ("vamgu", "g'lam") → pre-map nasal marks to "n" and addak to a doubled consonant ("vangu", "gallan"). Kanji get Chinese readings (known limitation). ASCII and accented Latin must be left untouched (only non-Latin runs are romanized).
- Google `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q=…` returns `[[["translated\n","source\n",…],…],…,"pa",…]`; joining segment[0]s and splitting on `\n` restores lines. Unofficial: may rate-limit.
- DeepL: `POST https://api-free.deepl.com/v2/translate` (keys ending `:fx`; others `api.deepl.com`), header `Authorization: DeepL-Auth-Key <key>`, JSON `{"text": [...], "target_lang": "EN-US"}` → `{"translations": [{"text": …}]}` (one per input).
- LibreTranslate: `POST <url>/translate` JSON `{"q": [...], "source": "auto", "target": "en", "format": "text"}` → `{"translatedText": [...]}`.

## Global Constraints

- Lyrics appear as soon as they are found; a translation fills in underneath when ready and never delays or blanks the lyrics. Translation failures just mean no line underneath.
- Translate only songs that are not already English; never send anything when the switch is off.
- The DeepL key is a credential: stored like the MA token (own file, mode 0600), never logged, never in settings.json.
- Settings stay fully usable with the remote: text fields start editing only on OK (Bigscreen's on-screen keyboard takes the arrows), the page scrolls to the focused row.
- Commit messages never mention Claude Code; they end with the Co-Authored-By line.

## Tasks

1. **`core/lyrics_text.py`** — `romanize(text) -> str` (non-Latin runs only, Gurmukhi/Devanagari nasal + addak fixes) and `is_english(lines) -> bool` (≥ 90% of letters Latin and ≥ 12% of words common English words). Tests: Punjabi lines from AZUL, Hindi, Cyrillic, accented Latin untouched, mixed lines, empty; English vs Punjabi vs Spanish vs mixed songs.
2. **`core/translate.py`** — `GoogleTranslator`, `DeepLTranslator(key)`, `LibreTranslator(url, api_key=None)`, each `async translate(lines: list[str]) -> list[str] | None` (one request per song, `None` unless exactly one result per line); `HttpClient.post_json`. Tests with fake HTTP: request shape per service, line-count mismatch → None, errors → None, DeepL free vs pro host.
3. **Settings + controller** — `AppSettings.lyrics_language` ("romanized" default), `lyrics_translate` (False), `translate_service` ("google"), `libretranslate_url`; DeepL key via `load_secret/save_secret("deepl_key")`. Controller: `lyricLines` items `{t, text, sub}`; English-only hides non-English songs; translation runs after lines are shown, only for non-English songs, cached per song+service, stale results dropped; properties/slots for each setting. Tests for each.
4. **QML** — LyricsView shows `sub` under a line (current line's at the "next line" size, others smaller); Settings page in a Flickable that follows focus; rows: Lyrics language (cycles), English underneath (on/off), Translation service (cycles, shown when on), DeepL key / LibreTranslate address (shown for that service); `TvField` edits only on OK. TV check with screenshots: Romanized AZUL, Original AZUL, English only (AZUL → artwork, an English song → lyrics), English underneath via Google on AZUL.
5. **Packaging + docs** — `anyascii` in `pyproject.toml`, `flatpak/requirements.txt`, regenerated `flatpak/python-deps.json`; README (settings, what is sent where, limitations); PR, CI, merge.
