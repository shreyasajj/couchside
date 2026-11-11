# Phase 4: Synced Lyrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show time-synced lyrics on Now Playing in the approved lyrics-forward layout (very large current line, auto-scrolling), from Music Assistant's metadata when it has them, otherwise from LRCLIB; fall back to the Phase 2 big-artwork layout when there are none; a Settings toggle turns lyrics off.

**Architecture:** `core/lyrics.py` (Qt-free) parses LRC, finds the line for a position, and fetches lyrics (MA track metadata → LRCLIB `get` → LRCLIB `search`) with an in-memory cache, using an injectable HTTP getter so it is testable. The controller fetches on every track change (stale results dropped) and exposes `hasLyrics` + `lyricLines`. QML adds a `LyricsView` and a compact header; `NowPlayingPage` switches layout on `app.hasLyrics && app.lyricsEnabled`. The progress tick that already drives the bar drives the highlighted line.

**Tech Stack:** Python 3.13, aiohttp (already a dependency of music-assistant-client), PySide6 6.11, QML.

**Spec:** [design](../specs/2026-11-10-couchside-design.md) "Now Playing = Layout B, lyrics-forward"; [Agents.md](../../../Agents.md) "Synced lyrics…", Settings "lyrics on/off".

**Branch:** `phase4-lyrics` from `main`.

## Verified (2026-11-11)

- MA 2.10.9 (schema 65): `metadata/get_track_lyrics` needs schema 101 → **not available**. Track objects do carry `metadata.lrc_lyrics` / `metadata.lyrics` (empty for the tracks checked); `music.get_item_by_uri(current_media.uri)` returns the track.
- LRCLIB `GET https://lrclib.net/api/get?artist_name&track_name&album_name&duration` returns `syncedLyrics` (LRC `[mm:ss.xx] text`), `plainLyrics`, `instrumental`, `duration`; 404 when not found. `GET /api/search?track_name&artist_name` returns a list. MA artist strings join artists with `/` ("Martin Garrix/Saksham/Scott Quinn"); LRCLIB matches on the first artist.
- LRCLIB asks clients to send a User-Agent naming the app: `Couchside/<version> (https://github.com/shreyasajj/couchside)`. No personal data is sent.

## Global Constraints

- Layout B sizes (design): current line ~6% of width (≈115 px at 1080p), bold, soft shadow; next line ~3.4%; the line after and the previous line smaller and faded; smooth auto-scroll; left-aligned; small sharp artwork (~10% width) with title and "artist · album" top-left.
- Hide the lyrics layer gracefully when none are found (no empty box, no flicker back and forth).
- Lyrics never block or slow playback controls; a failed or slow lookup just means no lyrics.
- No focus changes: lyrics are not focusable; the bottom bar keeps focus behaviour from Phases 2–3.
- Settings: "Show lyrics" on/off, saved in `settings.json`.
- Commit messages never mention Claude Code; they end with the Co-Authored-By line.

## Review Focus

1. **Track changes mid-lookup** (skip quickly through songs) → only the current song's lyrics ever show. (Task 2 `test_stale_lyrics_dropped`.)
2. **Malformed / odd LRC** (several timestamps on one line, `[offset:]`, metadata tags, blank lines, unsorted lines, hours) → parsed or skipped, never a crash. (Task 1 parser tests.)
3. **Plain (unsynced) lyrics only** → treated as no synced lyrics (big-artwork layout), not a frozen first line. (Task 1 `test_plain_only_is_none`.)
4. **LRCLIB down / slow / 404 / bad JSON** → no lyrics after a bounded wait (timeout 8 s), nothing retried in a loop. (Task 1 fetch tests.)
5. **Instrumental gaps and the time before the first line** → no line highlighted before the first timestamp; empty LRC lines show as a gap (♪). (Task 1 `test_index_before_first_line`, Task 3 TV check.)

---

### Task 1: Lyrics core

**Files:** Create `src/couchside/core/lyrics.py`; Test `tests/test_lyrics.py`.

**Interfaces — Produces:**
- `@dataclass(frozen=True) LyricLine(time: float, text: str)`.
- `parse_lrc(text: str | None) -> list[LyricLine]` — every `[mm:ss(.xx)]` (also `[h:mm:ss.xx]`) tag on a line yields a line; `[offset:+/-ms]` shifts all times (LRC: positive offset = lyrics earlier); other tags (`[ar:]`, `[ti:]`…) ignored; lines without a time tag ignored; result sorted by time; blank text kept as `""`.
- `line_index_at(lines, position: float) -> int` — index of the last line with `time <= position`, `-1` before the first.
- `first_artist(artist: str) -> str` — split on `/`, `,`, `&`, ` feat`, ` ft.`, ` x ` (case-insensitive), stripped.
- `@dataclass(frozen=True) TrackInfo(key, title, artist, album, duration, uri)`.
- `class LyricsFetcher(http_get, ma_lookup=None, timeout=8.0)`; `http_get(url, params) -> awaitable (status:int, json|None)`; `ma_lookup(uri) -> awaitable str|None` (LRC from MA). `async get(info) -> list[LyricLine] | None`:
  1. `ma_lookup(info.uri)` LRC if it parses to ≥ 1 line;
  2. LRCLIB `/api/get` with first artist, title, album, rounded duration;
  3. LRCLIB `/api/search` (track_name, artist_name) → the first result with `syncedLyrics` whose duration is within 3 s (or any synced one if duration unknown);
  4. else `None`. Instrumental → `None`. Cached by `info.key` (hits and misses); each step's exceptions/timeouts are swallowed.
- `async aiohttp_get(url, params) -> (status, json)` — real getter with the User-Agent, 8 s timeout.

- [ ] Step 1 tests: `test_parse_basic`, `test_parse_multiple_tags_one_line`, `test_parse_offset`, `test_parse_ignores_metadata_and_untimed`, `test_parse_sorts_and_keeps_blank`, `test_parse_hours`, `test_parse_garbage_is_empty`, `test_index_before_first_line`, `test_index_between_lines`, `test_first_artist`, `test_ma_lyrics_win`, `test_lrclib_get_used_with_first_artist`, `test_falls_back_to_search_by_duration`, `test_plain_only_is_none`, `test_instrumental_is_none`, `test_errors_and_timeouts_are_none`, `test_results_cached_including_misses`.
- [ ] Step 2 run → FAIL; Step 3 implement; Step 4 `.venv/bin/pytest -q` → pass; Step 5 commit `feat: lyrics parsing and lookup (MA metadata, LRCLIB)`.

### Task 2: Settings and controller

**Files:** Modify `src/couchside/core/settings.py`, `src/couchside/ui/controller.py`; Tests `tests/test_settings.py`, `tests/test_controller_props.py`.

**Interfaces — Produces:**
- `AppSettings.lyrics_enabled: bool = True` (type-checked load like the other fields).
- Controller: `lyricsChanged` signal; properties `hasLyrics: bool`, `lyricLines` (`[{t, text}]`), `lyricsEnabled: bool` (setter saves settings and emits); on each `NowPlaying` change whose track key (`uri` or `title|artist`) differs, clear lyrics and fetch (unless disabled); results for an older key are dropped. Track key, title, artist, album, duration come from the snapshot (add `uri` to `NowPlaying`).
- [ ] Tests: `test_lyrics_enabled_round_trip` (settings), `test_lyrics_fetched_on_track_change`, `test_stale_lyrics_dropped`, `test_lyrics_disabled_skips_fetch`, `test_same_track_does_not_refetch`.
- [ ] Commit `feat: fetch lyrics on track change, lyrics setting`.

### Task 3: Lyrics layout

**Files:** Create `src/couchside/ui/qml/LyricsView.qml`; Modify `NowPlayingPage.qml`, `SetupPage.qml` (Show lyrics toggle).

- `LyricsView`: `ListView` (not focusable, not interactive) of `lyricLines`; `currentIndex` = line for `position` (JS binary search, same rule as `line_index_at`); `highlightRangeMode: StrictlyEnforceRange`, `preferredHighlightBegin` ≈ 30% of height so the current line sits in the upper third; smooth `highlightMoveDuration` 400 ms. Delegate font: distance 0 → `0.06 * width` bold with shadow; +1 → `0.034 * width`, 85% opacity; others → `0.026 * width`, 45% opacity; previous lines fade to 35%. Empty line text → "♪". Before the first line, the view shows the first lines at "next" size.
- Now Playing: when `app.hasLyrics && app.lyricsEnabled`: compact header top-left (art 10% width, title 48 px bold, "artist · album" 30 px), `LyricsView` filling the middle, bar unchanged; otherwise the Phase 2 layout. Cross-fade 300 ms between layouts. Progress tick runs every 250 ms while lyrics show (500 ms otherwise).
- Settings: a "Show lyrics" switch row on the Settings page (D-pad reachable, OK toggles).
- [ ] TV check (keys via evemu, screenshots read): 1 a song with LRCLIB lyrics shows the lyrics layout, the current line large and in time with the music, scrolling; 2 Next to a song without lyrics → big-artwork layout, no flicker; 3 Previous → lyrics again (cache); 4 Settings → Show lyrics off → artwork layout; on → lyrics; 5 focus stays on the bar throughout; 6 CPU of the app while lyrics scroll (top) noted.
- [ ] Commit `feat: lyrics-forward Now Playing and lyrics toggle`.

### Task 4: Docs

- [ ] README: status → Phase 4; lyrics section (sources, toggle, privacy: title/artist/album/duration go to lrclib.net); API notes (no `get_track_lyrics` before schema 101; LRCLIB first-artist matching). Commit `docs: phase 4`.
