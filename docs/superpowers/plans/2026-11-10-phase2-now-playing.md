# Phase 2: Now Playing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Phase 1 home screen with the approved Now Playing screen: blurred artwork background, large artwork and metadata, and a remote-friendly bottom bar with progress, shuffle, previous, play/pause, next, repeat, volume and settings.

**Architecture:** `core/playback.py` grows from "title + state" to a full `NowPlaying` snapshot built from the active MA player and its queue (progress, duration, shuffle, repeat, volume, palette), plus queue/volume commands. `core/format.py` holds the pure helpers (time text, art URL sizing, palette colour). The controller exposes them as properties; QML ticks the progress bar locally between server updates. Lyrics are Phase 4, so this phase builds the design's **no-lyrics layout** (big artwork left, large title); Phase 4 adds the lyrics-forward variant on top.

**Tech Stack:** Python 3.13, PySide6 6.11, QML + Kirigami, `QtQuick.Effects.MultiEffect` (blur), music-assistant-client 1.8.0.

**Spec:** [docs/superpowers/specs/2026-11-10-couchside-design.md](../specs/2026-11-10-couchside-design.md) ("Now Playing = Layout B"), base brief [Agents.md](../../../Agents.md) (Now Playing, TV/10-foot UX).

**Branch:** `phase2-now-playing`, cut from `phase1-foundation` after its final-review fixes are committed.

## Global Constraints

- Every action reachable with D-pad + OK + Back only; clear, high-contrast focus ring (`#4fc3f7`, offset) on the focused element; focus never gets lost.
- Minimum body text ~28px at 1080p; titles larger. All sizes are `n * u` where `u = height / 1080`.
- Back always goes to the previous screen; Back on Now Playing exits after a confirm (exists from Phase 1).
- Media keys (play/pause, next, previous, **volume**) work anywhere in the app.
- Never crash on a missing MA server or missing fields: every MA field read is optional.
- No-lyrics layout sizes (design): big artwork ~33% of width, title ~4.6% of width.
- Bottom bar order (design): progress line, elapsed / −remaining, then shuffle, previous, play/pause (larger, filled), next, repeat, volume.
- Blurred full-screen artwork background, darkened toward the bottom.
- Commit messages never mention Claude Code; they end with the Co-Authored-By line.

## Review Focus

1. **Stream with no duration** (radio, live) → progress bar hidden, elapsed only, no "−" time, no division by zero. (Task 1 `test_progress_without_duration`, Task 2 `test_format_time`.)
2. **Track changes while paused or idle** → progress shows the new track's position and does not tick; nothing from the previous track lingers. (Task 1 `test_progress_from_queue_when_paused`.)
3. **No artwork** → no broken image; the background falls back to the album palette colour or the app's default gradient. (Task 2 `test_palette_colour_missing`, Task 4 visual check.)
4. **Player without volume control** (`volume_control == "none"`) → volume button hidden, volume keys do nothing, focus chain skips it. (Task 1 `test_volume_unavailable`.)
5. **Focus after a popup or page closes** (volume popup, settings, exit dialog) → focus returns to the button that opened it, never to nothing. (Task 4 TV check list.)

---

### Task 1: NowPlaying snapshot with progress, queue modes and volume

**Files:**
- Modify: `src/couchside/core/playback.py`
- Test: `tests/test_playback.py`

**Interfaces:**
- Consumes: `Playback`, `ConnState` from Phase 1; MA models (verified live on 2.10.9): `player.current_media` has `title artist album image_url duration elapsed_time elapsed_time_last_updated palette queue_item_id`; `player.active_source` is the queue id (equals `player_id` for MA's own queue); `client.player_queues.get(queue_id)` returns a cached `PlayerQueue` with `state elapsed_time elapsed_time_last_updated shuffle_enabled repeat_mode current_item.duration`; `player.volume_level` (0–100), `player.volume_control` (`"none"` when not controllable).
- Produces:
  - `NowPlaying` gains: `duration: float | None`, `elapsed: float`, `elapsed_at: float` (server epoch seconds of `elapsed`), `shuffle: bool`, `repeat: Literal["off","all","one"]`, `volume: int | None` (None = no volume control), `palette_dark: tuple[int,int,int] | None`, `queue_id: str | None`. Existing fields unchanged. All new fields have defaults so Phase 1 tests keep constructing it.
  - `position_at(np: NowPlaying, now: float) -> float`: `elapsed` plus `now - elapsed_at` when `state == "playing"`, else `elapsed`; clamped to `[0, duration]` (only the lower bound when `duration` is None).
  - `Playback.toggle_shuffle()`, `Playback.cycle_repeat()` (off → all → one → off), `Playback.set_volume(level: int)` (clamped 0–100), `Playback.step_volume(delta: int)`: async, no-ops unless CONNECTED with an active player (same guard as `_command`). Shuffle/repeat go to `client.player_queues.shuffle/repeat(queue_id, …)`; volume to `client.players.volume_set(player_id, level)`.

- [ ] **Step 1: Write the failing tests** (extend the fakes with `players.volume_set`, a `player_queues` fake with `get/shuffle/repeat`, and queue/player fields)

```python
def test_progress_from_queue_when_paused():
    # queue elapsed wins over current_media's; paused => no ticking
    np = make_playing(queue=queue(state="idle", elapsed=42.0, at=1000.0), media_elapsed=3.0, duration=261)
    assert np.elapsed == 42.0 and np.duration == 261
    assert position_at(np, now=1010.0) == 42.0

def test_position_ticks_while_playing():
    np = NowPlaying("t", "a", "b", None, "playing", duration=200, elapsed=10.0, elapsed_at=1000.0)
    assert position_at(np, 1005.5) == 15.5
    assert position_at(np, 2000.0) == 200          # clamped to duration
    assert position_at(np, 990.0) == 10.0 - 0 or position_at(np, 990.0) >= 0  # never negative

def test_progress_without_duration():
    np = NowPlaying("radio", "", "", None, "playing", duration=None, elapsed=5.0, elapsed_at=0.0)
    assert position_at(np, 100.0) == 105.0

def test_progress_falls_back_to_current_media_without_queue():
    np = make_playing(queue=None, media_elapsed=7.0, media_at=500.0, duration=180)
    assert (np.elapsed, np.elapsed_at, np.duration) == (7.0, 500.0, 180)

def test_shuffle_repeat_volume_read():
    np = make_playing(queue=queue(shuffle=True, repeat="one"), volume=35)
    assert (np.shuffle, np.repeat, np.volume) == (True, "one", 35)

def test_volume_unavailable():
    assert make_playing(volume=35, volume_control="none").volume is None

async def test_cycle_repeat_sends_next_mode():  # off -> all -> one -> off
async def test_toggle_shuffle_sends_inverse():
async def test_set_volume_clamps():               # set_volume(130) sends 100; step_volume(-5) from 3 sends 0
async def test_queue_commands_noop_when_disconnected():
```

Write the bodies of the async tests against the fakes' recorded calls, e.g. `assert conn.client.player_queues.calls == [("repeat", "q1", RepeatMode.ALL)]`.

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_playback.py -q`
Expected: FAIL (`position_at` not defined / unexpected keyword `duration`).

- [ ] **Step 3: Implement** in `src/couchside/core/playback.py`: new fields, `position_at`, queue lookup (`client.player_queues.get(active.active_source or active.player_id)`, guarded so a missing `player_queues` or `None` queue falls back to `current_media`), repeat mapped from `RepeatMode` (`"unknown"` → `"off"`), commands above. Keep `refresh()`'s change-detection; the snapshot is a frozen dataclass so equality still works.

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/pytest -q`
Expected: all tests pass (62 from Phase 1 + new).

- [ ] **Step 5: Commit**

```bash
git add src/couchside/core/playback.py tests/test_playback.py
git commit -m "feat: now playing snapshot with progress, shuffle, repeat and volume"
```

### Task 2: Display helpers

**Files:**
- Create: `src/couchside/core/format.py`
- Test: `tests/test_format.py`

**Interfaces:**
- Produces:
  - `format_time(seconds: float | None) -> str`: `"0:00"` for None/negative; `"m:ss"` under an hour; `"h:mm:ss"` from an hour.
  - `art_url(url: str | None, size: int) -> str`: `""` for None; for MA image-proxy URLs (`/imageproxy/` in the path) replace or add the `size` query parameter; other URLs unchanged.
  - `palette_colour(rgb: tuple[int,int,int] | None, fallback: str = "#0d0b1a") -> str`: `"#rrggbb"`, or `fallback` for None/invalid.

- [ ] **Step 1: Write the failing tests**

```python
def test_format_time():
    assert format_time(None) == "0:00"
    assert format_time(-3) == "0:00"
    assert format_time(5.9) == "0:05"
    assert format_time(261) == "4:21"
    assert format_time(3725) == "1:02:05"

def test_art_url_resizes_imageproxy():
    u = "http://h:8095/imageproxy/abc?size=512&fmt=jpg"
    assert art_url(u, 1024) == "http://h:8095/imageproxy/abc?size=1024&fmt=jpg"
    assert art_url("http://h:8095/imageproxy/abc", 300) == "http://h:8095/imageproxy/abc?size=300"

def test_art_url_leaves_other_urls():
    assert art_url("https://i.scdn.co/image/x", 1024) == "https://i.scdn.co/image/x"
    assert art_url(None, 1024) == ""

def test_palette_colour():
    assert palette_colour((25, 28, 41)) == "#191c29"

def test_palette_colour_missing():
    assert palette_colour(None) == "#0d0b1a"
    assert palette_colour((300, -1, 2)) == "#0d0b1a"
```

- [ ] **Step 2: Run to verify they fail** — `.venv/bin/pytest tests/test_format.py -q` → FAIL (module not found).
- [ ] **Step 3: Implement** `format.py` with `urllib.parse` for `art_url`.
- [ ] **Step 4: Run** — `.venv/bin/pytest -q` → all pass.
- [ ] **Step 5: Commit** — `git commit -m "feat: time, artwork size and palette helpers"`

### Task 3: Controller properties and slots

**Files:**
- Modify: `src/couchside/ui/controller.py`
- Test: `tests/test_controller_props.py` (skips cleanly when PySide6 is not importable, so it runs inside the Flatpak and on any dev machine with PySide6)

**Interfaces:**
- Consumes: Task 1 `NowPlaying` fields and commands; Task 2 helpers.
- Produces (QML-facing, all `notify=changed`):
  - `artUrl` → `art_url(image_url, 600)`; new `artUrlLarge` → `art_url(image_url, 1024)` (background).
  - `duration: float` (0 when unknown), `hasDuration: bool`, `positionBase: float`, `positionAt: float` (epoch seconds), `shuffle: bool`, `repeatMode: str`, `volume: int` (-1 when unavailable), `hasVolume: bool`, `backgroundColour: str` (palette_colour).
  - Slots: `toggleShuffle()`, `cycleRepeat()`, `setVolume(int)`, `volumeUp()` / `volumeDown()` (±5), `formatTime(float) -> str`.
  - Progress is ticked in QML: `position = clamp(positionBase + (Date.now()/1000 - positionAt))` while `isPlaying`.

- [ ] **Step 1: Write the failing tests**: build `AppController` with a fake connection whose playback snapshot is a fixed `NowPlaying`; assert `hasDuration`, `volume == -1` when `volume is None`, `artUrlLarge` contains `size=1024`, `formatTime(261) == "4:21"`, and that `cycleRepeat()` schedules `Playback.cycle_repeat` (patch it with an async stub recording calls; run the loop once).
- [ ] **Step 2: Run** inside the Flatpak on the TV (`scripts/dev-deploy.sh` then `flatpak run --command=python3 … -m pytest tests/test_controller_props.py`) → FAIL (missing properties).
- [ ] **Step 3: Implement** the properties and slots.
- [ ] **Step 4: Run** the same command → PASS; `.venv/bin/pytest -q` on the Mac → all pass (controller test skipped there if no PySide6).
- [ ] **Step 5: Commit** — `git commit -m "feat: expose progress, modes, volume and palette to QML"`

### Task 4: Now Playing screen

**Files:**
- Create: `src/couchside/ui/qml/NowPlayingPage.qml`, `ProgressBar.qml`, `VolumePopup.qml`, `ArtBackground.qml`
- Modify: `src/couchside/ui/qml/Main.qml` (initial page, volume key shortcuts), `FocusButton.qml` (`active` state for shuffle/repeat: accent dot under the icon; small badge "1" for repeat-one)
- Delete: `src/couchside/ui/qml/HomePage.qml`

**Interfaces:**
- Consumes: Task 3 properties/slots; Phase 1 `FocusButton`, `goBack()`, `focusDefault()` convention, `PairingOverlay`, exit dialog.

Layout (1080p numbers, all `* u`):
- **ArtBackground**: `artUrlLarge` image, `PreserveAspectCrop`, `MultiEffect` blur (`blurEnabled`, `blur: 1.0`, `blurMax: 64`), cross-fade (400 ms) between tracks by swapping two Image layers; base colour `backgroundColour` underneath; dark scrim gradient from 35% black at top to 85% black at the bottom. No image → base colour plus scrim only.
- **No-lyrics layout**: artwork card left, width 33% of window, square, radius 16, soft shadow; to its right a column vertically centred: title (`0.046 * width` px, bold, max 2 lines, elide), "artist" (48), "album" (36, 70% opacity). Phase 4's lyrics layout will switch on a `hasLyrics` flag, so keep this column in its own `Item` with `visible: true` for now.
- **Status banner**: top-left, `statusText` in amber (32), shown only when non-empty. "Nothing playing" (title slot) when connected with no media.
- **Bottom bar**: `ProgressBar` (thin track 6, knob-less, fills to `position/duration`; hidden when `!hasDuration`), then `elapsed` left / `−remaining` right (28). Below, a centred row: shuffle, previous, play/pause (primary), next, repeat, volume (hidden when `!hasVolume`), and a settings button at the far right of the row separated by extra space.
- **Focus**: Left/Right move along the row (KeyNavigation chain computed so hidden buttons are skipped); Up/Down do nothing on the row; default focus = play/pause on page open and after any popup/page closes; settings button remembers it opened setup and focus returns to it on Back.
- **VolumePopup**: OK on the volume button opens a horizontal bar above it (value 0–100, big number); Left/Right = ∓/±5 via `setVolume`; OK or Back closes and returns focus to the volume button; auto-closes after 4 s idle. Remote volume keys (`Volume Up`, `Volume Down` shortcuts in Main.qml) call `volumeUp/Down` and flash the popup without taking focus.
- **Progress tick**: a 500 ms `Timer` running only while `isPlaying` and the window is visible.

- [ ] **Step 1: Deploy and verify on the TV** (no automated QML tests; the visual checks are the test). `scripts/dev-deploy.sh --run`, then with music queued (search a track as in Phase 1's live check):
  1. Background shows blurred artwork, darker at the bottom; artwork, title, artist, album readable from across the room.
  2. Progress moves each second while playing, stops when paused, jumps to 0:00 on next; times are `m:ss`.
  3. Shuffle and repeat toggle on screen and in the MA web app; repeat cycles off → all → one.
  4. Volume popup: opens on OK, Left/Right change the TV speaker volume in MA, closes on OK/Back/4 s, focus back on the volume button.
  5. Settings button opens setup; Back returns with focus on the settings button.
  6. Exit dialog still works; focus back on play/pause after Cancel.
  7. Play a radio station (no duration): no progress bar, elapsed only.
  8. A track without artwork: palette or default background, no broken image.
  Screenshot each with `spectacle -b -n -f -o /tmp/…png` and look at them.
- [ ] **Step 2: Commit** — `git commit -m "feat: now playing screen with blurred artwork and control bar"`

### Task 5: Docs and phase check

**Files:**
- Modify: `README.md` (status line → Phase 2; remote section: volume popup, shuffle/repeat; API notes: `current_media.palette`, image proxy `size` parameter, queue vs. player `elapsed_time`).

- [ ] **Step 1:** Update the README; run `.venv/bin/pytest -q` → all pass.
- [ ] **Step 2: Commit** — `git commit -m "docs: phase 2 now playing"`
