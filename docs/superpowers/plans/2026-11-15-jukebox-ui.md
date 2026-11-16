# Jukebox UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Couchside the look and layout of the "Bigscreen Jukebox" mockup while keeping every feature, and add a list picker for the Sendspin output and a choice of beat source for the visualizer.

**Architecture:** The `AppController` (`app` in QML) stays the only bridge. A new Qt-free module lists PipeWire outputs and sources through `pactl`; the beat detector also produces a 64-bar spectrum. In QML, `Main.qml` becomes a shell: a persistent `TopBar` over one `Loader` that swaps screens; screens become plain `FocusScope`s instead of pushed `Kirigami.Page`s. Navigation rules that can be wrong live in `nav.js` so they are tested without Kirigami.

**Tech Stack:** Python 3.12, PySide6 (QML, Qt Quick Canvas), Kirigami window, numpy, sounddevice/PortAudio, `pactl` (in the KDE runtime), pytest.

**Spec:** `docs/superpowers/specs/2026-11-15-jukebox-ui-design.md`. Visual reference: `Bigscreen Jukebox.dc.html` (moved to `docs/design/` in Task 11).

## Global Constraints

- Colours: background `#07070b`, accents `a1 #00e0c6`, `a2 #ff3da6`; focus is a 3 px `a1` ring with a soft glow, never a white fill.
- No text the viewer must read below 28 px at 1080p (24 px allowed only for durations and counts). All sizes are multiplied by `u` (window height / 1080).
- Font: Noto Sans, weights 500-800.
- Every control reachable with D-pad, OK, Back. Unhandled Up from a screen's top row goes to the top bar.
- No WebEngine, no new Python dependencies.
- Visualizer: draw at no more than 1280×720 scaled up, at most 30 fps, timer stopped when the screen is not in front or the app is not active. No per-frame full-screen blur.
- The audio stream is open only while something on screen uses it and music plays.
- Run tests with `.venv/bin/python -m pytest -q` (396 pass before this work). Kirigami is not installed on the dev Mac: anything importing `org.kde.kirigami` is checked on the TV with `scripts/dev-deploy.sh --run` (`mediac@192.168.30.153`).
- Commit messages and PR text never mention Claude or Claude Code; no co-author trailer.
- The old UI is tagged `pre-jukebox-ui` (commit `ff3f763`).

## Review Focus

1. A saved output or beat source that no longer exists (HDMI unplugged, USB mic removed): playback and the visualizer fall back to automatic, the saved entry stays visible in the list, and a toast says so. (Tasks 1, 3)
2. `pactl` missing, timing out or printing something that is not JSON: both lists still open with "Default" / "What this TV is playing" and the direct devices. (Task 1)
3. The screen you are on loses its tab (Show lyrics or the visualizer switched off, by a setting or an update): you land on Now Playing with focus on play/pause. (Task 5)
4. Nothing playing or the server gone: `spectrum` is 64 zeros, Now Playing, Lyrics and Visualizer show their empty state, and focus still lands somewhere visible. (Tasks 3, 6, 8, 9)
5. Very long text (track title, speaker name in the "Playing on" chip, output descriptions): elided, never pushing the top bar or a row past its width. (Task 4)

---

## File structure

Created:
- `src/couchside/core/audio_devices.py`: list and name outputs and beat sources.
- `src/couchside/ui/qml/TopBar.qml`, `Chip.qml`, `QrCard.qml`, `FocusRing.qml`, `GradientFill.qml`
- `src/couchside/ui/qml/LyricsPage.qml`, `VisualizerPage.qml`, `viz.js`, `nav.js`
- `tests/test_audio_devices.py`, `tests/test_nav_js.py`, `tests/test_viz_js.py`, `tests/test_topbar_qml.py`, `tests/qml/TopBarHarness.qml`

Modified: `core/settings.py`, `core/beat.py`, `core/audio_capture.py`, `sendspin/runner.py`, `ui/controller.py`, every file in `ui/qml/`, `web/guest.html`, `README.md`, `pyproject.toml` (package-data already covers `*.qml`/`*.js`), their tests.

Removed: `PartyView.qml` (its content moves into `VisualizerPage.qml`), `PageBackground.qml` if nothing uses it after Task 10.

---

### Task 1: Outputs and beat sources (Qt-free)

**Files:** Create `src/couchside/core/audio_devices.py`, `tests/test_audio_devices.py`. Modify `src/couchside/core/settings.py`, `src/couchside/sendspin/runner.py`, `tests/test_settings.py`, `tests/test_runner.py`.

**Interfaces — Produces:**

```python
# core/audio_devices.py
@dataclass(frozen=True)
class AudioChoice:
    id: str        # "" = automatic; "sink:<name>"; a direct device name; a source name
    label: str
    section: str   # "" | "Direct (visualizer can't listen)" | "Outputs" | "Inputs"

def parse_sinks(text: str) -> list[AudioChoice]      # id "sink:<name>", label = description
def parse_sources(text: str) -> list[AudioChoice]    # id = name; "*.monitor" -> section "Outputs",
                                                     # label = description without a leading "Monitor of "
async def pactl_json(kind: str, timeout: float = 5.0) -> str   # kind "sinks"|"sources"; "" on any failure
def output_choices(sinks: list[AudioChoice], direct: list[str], saved: str | None) -> list[AudioChoice]
def source_choices(sources: list[AudioChoice], saved: str | None) -> list[AudioChoice]
def capture_source(visualizer_source: str | None, output: str | None,
                   sources: list[AudioChoice] | None = None) -> str
```

- `output_choices`: first `AudioChoice("", "Default", "")`, then sinks, then direct names (minus `pulse`, `default`, `hdmi` aliases stay as given by `parse_audio_devices`, but `pulse` is dropped) in section `"Direct (visualizer can't listen)"`. A `saved` value not in the list is appended with label `"<name> (not connected)"`.
- `source_choices`: first `AudioChoice("", "What this TV is playing", "")`, then monitors, then inputs; unknown `saved` appended the same way.
- `capture_source`: explicit `visualizer_source` wins when `sources` is None or contains it; else `"<name>.monitor"` for output `"sink:<name>"`; else `"@DEFAULT_MONITOR@"`.
- `AppSettings` gains `visualizer_source: str | None = None`, `visualizer_intensity: float = 1.0`, `visualizer_mode: str = "radial"`, `accent: str = "teal-pink"`. `load_settings` must accept an int for a float field.
- `build_daemon_argv`: for `sendspin_audio_device == "sink:X"` the argv is `["env", "PULSE_SINK=X", sys.executable, "-c", DAEMON_ENTRY, "daemon", …, "--audio-device", "pulse"]`; other values unchanged.

- [ ] **Step 1: Failing tests** in `tests/test_audio_devices.py`:

```python
SINKS = '[{"name":"alsa_output.hdmi","description":"HDMI Surround","monitor_source":"alsa_output.hdmi.monitor"}]'
SOURCES = ('[{"name":"alsa_input.usb","description":"USB Mic"},'
           '{"name":"alsa_output.hdmi.monitor","description":"Monitor of HDMI Surround"}]')

def test_parse_sinks():
    assert parse_sinks(SINKS) == [AudioChoice("sink:alsa_output.hdmi", "HDMI Surround", "Outputs")]

def test_parse_sources_splits_monitors_and_inputs():
    assert parse_sources(SOURCES) == [
        AudioChoice("alsa_output.hdmi.monitor", "HDMI Surround", "Outputs"),
        AudioChoice("alsa_input.usb", "USB Mic", "Inputs")]

@pytest.mark.parametrize("text", ["", "not json", "{}", "[1, null, {\"x\": 1}]"])
def test_garbage_gives_no_choices(text):
    assert parse_sinks(text) == [] and parse_sources(text) == []

def test_output_choices_order_and_missing_saved():
    got = output_choices(parse_sinks(SINKS), ["HD-Audio Generic: HDMI 1 (hw:0,7)", "pulse"], "sink:gone")
    assert [c.id for c in got] == ["", "sink:alsa_output.hdmi", "HD-Audio Generic: HDMI 1 (hw:0,7)", "sink:gone"]
    assert got[-1].label == "gone (not connected)"

def test_source_choices_default_first():
    assert source_choices([], None) == [AudioChoice("", "What this TV is playing", "")]

def test_capture_source():
    assert capture_source(None, None) == "@DEFAULT_MONITOR@"
    assert capture_source(None, "sink:alsa_output.hdmi") == "alsa_output.hdmi.monitor"
    assert capture_source(None, "HD-Audio Generic: HDMI 1 (hw:0,7)") == "@DEFAULT_MONITOR@"
    assert capture_source("alsa_input.usb", "sink:x") == "alsa_input.usb"
    assert capture_source("gone", "sink:x", parse_sources(SOURCES)) == "x.monitor"   # Review Focus 1

async def test_pactl_missing_returns_empty(monkeypatch):   # Review Focus 2
    monkeypatch.setenv("PATH", "/nonexistent")
    assert await pactl_json("sinks") == ""
```

In `tests/test_runner.py`: `build_daemon_argv(AppSettings(sendspin_audio_device="sink:alsa_output.hdmi"), d)` starts with `["env", "PULSE_SINK=alsa_output.hdmi"]` and ends with `["--audio-device", "pulse"]`. In `tests/test_settings.py`: defaults of the four new fields; `{"visualizer_intensity": 2}` loads as `2.0`; `{"visualizer_intensity": "x"}` keeps `1.0`.

- [ ] **Step 2:** Run `.venv/bin/python -m pytest tests/test_audio_devices.py tests/test_runner.py tests/test_settings.py -q`; expect failures on the new names.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Same command passes; full suite passes.
- [ ] **Step 5:** Commit `feat: list PipeWire outputs and beat sources; Sendspin can play to a chosen output`.

### Task 2: Spectrum and a chosen capture source

**Files:** Modify `src/couchside/core/beat.py`, `src/couchside/core/audio_capture.py`, `tests/test_beat.py`, `tests/test_audio_capture.py`.

**Interfaces — Produces:**
- `BeatDetector.bars: numpy.ndarray`: 64 float32 values in `[0, 1.15]`, updated by every `feed`; log-spaced bands from 40 Hz to 10 kHz (each band at least one FFT bin), level against the same slowly falling peak idea as `level` so quiet and loud music both fill the range; all zeros in silence. `feed`'s return value is unchanged.
- `open_monitor_stream(callback, source: str = "@DEFAULT_MONITOR@")` sets `PULSE_SOURCE` to `source`.
- `AudioPulse(..., source: str = "@DEFAULT_MONITOR@")`; attribute `source`; `set_source(source: str) -> None` (no-op when equal; when running: stop, then start again, clearing the failed-open back-off); attribute `bars: list[float]` (64 values; zeros when stopped). `open_stream` is now called as `open_stream(callback, source)`.

- [ ] **Step 1: Failing tests.** `test_beat.py`: silence → `bars` all `0`; a 100 Hz sine at 22050 Hz → `argmax(bars) < 16`; a 5 kHz sine → `argmax(bars) >= 40`; white noise at amplitude 1.0 → `0 <= bars.min()` and `bars.max() <= 1.15`; `len(bars) == 64`. `test_audio_capture.py`: the fake opener records `source`; `AudioPulse(source="a.monitor")` opens with `"a.monitor"`; `set_source("b")` while running closes the first stream and opens a second with `"b"`; `set_source` after a failed open retries at once; `bars` is 64 zeros after `stop()`.
- [ ] **Step 2:** Run both files; expect failures.
- [ ] **Step 3:** Implement. Update existing fakes in `test_audio_capture.py` to take `(callback, source)`.
- [ ] **Step 4:** Both files and the full suite pass.
- [ ] **Step 5:** Commit `feat: spectrum bars from the beat detector; the visualizer can listen to a chosen source`.

### Task 3: Controller API

**Files:** Modify `src/couchside/ui/controller.py`, `tests/test_controller_props.py`.

**Interfaces — Consumes:** Task 1 and 2 names. **Produces (QML-facing):**

| Name | Type | Notes |
|---|---|---|
| `audioOutputs` | list of `{id, label, section, current}` | notify `sendspinChanged` |
| `audioOutputLabel` | str | label of the saved output |
| `setAudioOutput(id: str)` | slot | `""` saves `None`; saving restarts the daemon (supervisor) and re-points the capture source |
| `beatSources` | list of `{id, label, section, current}` | notify `pulseChanged` |
| `beatSourceLabel` | str | |
| `setBeatSource(id: str)` | slot | saves `visualizer_source`, calls `AudioPulse.set_source` |
| `loadAudioDevices()` | slot | now loads sinks, sources and direct devices together |
| `visualizerIntensity` | float rw | clamped 0-2.4, rounded to 0.05, saved |
| `visualizerMode` | str rw | `radial` \| `flow` \| `bars` \| `party`, saved |
| `vizVisible` | bool rw | QML: the Visualizer screen is in front |
| `spectrum` | list of 64 floats | notify `spectrumChanged` |
| `vizBeat`, `vizEnergy` | float | notify `spectrumChanged`; beat = 1.0 on a beat, ×0.75 per frame; energy = detector level |
| `accents` | list of `{id, label, a1, a2, current}` | `teal-pink` (#00e0c6/#ff3da6), `sky-coral` (#36d6ff/#ff5d3d), `violet` (#7c5cff/#b14dff), `gold-green` (#ffd23d/#23d18b) |
| `accent1`, `accent2` | str | notify `accentChanged` |
| `setAccent(id: str)` | slot | unknown ids ignored |

Removed: `cycleAudioDevice`, `audioDevice`, `partyMode`, `togglePartyMode` (party is `visualizerMode == "party"` on the Visualizer screen). `lightPulse`, `beatHue`, `audioPulse`, `partyLights`, `visualizerEnabled`, `pulseVisible` stay.

Listening rule: listen while music plays and (`pulseVisible and visualizer_enabled`) or `vizVisible`. While `vizVisible`, the poll timer runs every 33 ms and emits `spectrumChanged` each tick; otherwise 50 ms as today and `spectrum` is not emitted. When a saved beat source is not among the loaded sources, capture uses the automatic source and a toast says `"<label> isn't connected — listening to what this TV plays"` once per load.

- [ ] **Step 1: Failing tests** (stub `_pulse` with a fake that records `start/stop/set_source` and has `level`, `beats`, `bars`):
  - `setAudioOutput("sink:a")` saves `"sink:a"`, `audioOutputLabel` is the sink's label, and the fake pulse got `set_source("a.monitor")`; `setAudioOutput("")` saves `None`.
  - `setBeatSource("mic")` saves it and calls `set_source("mic")`; with sources loaded that lack the saved one, `set_source` gets the automatic source and `toast` is non-empty (Review Focus 1).
  - With no sinks/sources loaded, `audioOutputs[0] == {"id": "", "label": "Default", "section": "", "current": True}` and `beatSources[0]["label"] == "What this TV is playing"` (Review Focus 2).
  - `spectrum` is 64 zeros when nothing plays (Review Focus 4); with `vizVisible = True` and music playing the fake pulse is started even when `visualizer_enabled` is False; setting `vizVisible = False` stops it.
  - `visualizerIntensity = 9` reads back `2.4`; `= 0.52` reads back `0.5`; `visualizerMode = "nope"` is ignored.
  - `setAccent("violet")` → `accent1 == "#7c5cff"`, saved; `setAccent("x")` changes nothing.
- [ ] **Step 2:** Run `tests/test_controller_props.py`; expect failures.
- [ ] **Step 3:** Implement; delete or rewrite tests of the removed names.
- [ ] **Step 4:** Full suite passes.
- [ ] **Step 5:** Commit `feat: controller exposes output and beat-source lists, spectrum, visualizer mode and intensity, accent colours`.

### Task 4: Theme and shared controls

**Files:** Modify `Theme.qml`, `FocusButton.qml`, `ListRow.qml`, `PillButton.qml`, `MediaCardItem.qml`, `Toast.qml`, `ActionSheet.qml`, `TrackProgress.qml`, `UpNext.qml`, `qmldir`. Create `FocusRing.qml`, `GradientFill.qml`, `Chip.qml`. Tests: `tests/qml/BlocksHarness.qml`, `tests/test_blocks_qml.py`, `tests/qml/SheetHarness.qml`, `tests/test_action_sheet_qml.py`.

**Interfaces — Produces:**
- `Theme`: `bg "#07070b"`, writable `a1`, `a2` (defaults teal/pink), `text`, `textDim` (white 62 %), `textFaint` (white 45 %), `surface` (white 5 %), `surfaceHigh` (white 10 %), `border` (white 10 %), `panel` (`#800a0a10`), `ink "#06121a"` (text on the gradient), `warn`, `fontFamily "Noto Sans"`, sizes `display 84`, `subtitle 38`, `rowTitle 42`, `tab 30`, `body 32`, `label 28`, `small 24`, `margin 56`, `radius 22`, `focusMs`, `fadeMs`. The old names `accent`, `focus`, `focusText` are removed; every use is replaced.
- `GradientFill { radius }`: a rectangle filled left-to-right `a1 → a2`.
- `FocusRing { target; radius }`: 3 px `a1` border plus an outer soft glow, visible when `target.activeFocus`.
- `Chip { text; dotColor; active; u; signal clicked }`: pill button (focusable, OK activates), text elides at `maximumWidth` (default `420*u`).
- `FocusButton`: same properties as today; `primary` is the gradient circle (116 px) with dark icon; others are bare icons; focus = `FocusRing`; `active` tints the icon `a1`.
- `ListRow`: same properties; base = surface fill + border; focused = teal-to-pink tinted fill, 2 px `a1` border, scale 1.012, text stays white; gains `property string hint` (e.g. "PLAY") shown at the right only when focused.
- `ActionSheet.open(title, actions, returnTo, callback)`: actions may carry `checked: true` (a tick in `a1`) and `section: "…"` (a small heading before the first action of each section); the sheet opens with focus on the checked action when there is one. Long lists scroll.

- [ ] **Step 1: Failing tests.** In the blocks test: the focused `ListRow`'s title colour is `Theme.text` (white) and its `hint` item is visible only with focus; `Chip` with an 80-character text has `width <= 420` (Review Focus 5) and emits `clicked` on Return; `FocusButton` primary has `width == 116`. In the sheet test: with `[{id:"a"},{id:"b",checked:true}]` the focused action after `open` is `b`; a `section` value produces a visible heading item.
- [ ] **Step 2:** Run the two QML test files; expect failures.
- [ ] **Step 3:** Implement the controls to the mockup's values (search rows: `Bigscreen Jukebox.dc.html` `baseRow`/`focusedRow`; play button: lines 111-124; tab focus ring: `focusRing`).
- [ ] **Step 4:** QML tests and the full suite pass.
- [ ] **Step 5:** Commit `feat: Jukebox theme and shared controls`.

### Task 5: Shell and top bar

**Files:** Create `TopBar.qml`, `QrCard.qml`, `nav.js`, `tests/test_nav_js.py`, `tests/test_topbar_qml.py`, `tests/qml/TopBarHarness.qml`. Modify `Main.qml`, every `*Page.qml` (root `Kirigami.Page` → `FocusScope` with the same `focusDefault()`/`handleBack()` functions; drop `globalToolBarStyle`, `padding`, `isCurrentPage`), `QrCode.qml`.

**Interfaces — Produces:**

```js
// nav.js (.pragma library)
function tabs(lyricsOn, visualizerOn)   // -> ["now","search","queue","lyrics","visualizer"] minus hidden ones
function isTab(screen)
function validScreen(screen, lyricsOn, visualizerOn)   // -> screen, or "now" when its tab is hidden
function back(screen, lastTab)   // -> "now" | lastTab | "exit": non-tab screens return lastTab,
                                 //    tabs other than "now" return "now", "now" returns "exit"
```

- `TopBar { u; screen; tabs; speakerName; guestMode; signal go(string screen); signal toggleGuest(); signal leaveDown() }`; function `focusCurrent()`. Items left to right: tabs, "Playing on <b>name</b> ▾" chip (`go("speakers")`), Guest chip (`toggleGuest()`, hidden while `guestMode`), gear (`go("settings")`). Left/Right move, no wrap; Down emits `leaveDown`; Up does nothing; the active tab has the gradient underline. Tab labels: Now Playing, Search, Queue, Lyrics, Visualizer.
- `QrCard { u; rows; caption; url; signal clicked }`: white card, 176 px QR, caption 24 px bold dark, URL in teal; focusable; in `Main.qml` it sits top-right over every screen while `app.guestMode`, and OK opens `"guests"`. The top bar's right cluster gets right padding of the card's width + 24 while it is shown.
- `Main.qml`: `property string screen: "now"`, `property string lastTab: "now"`, `function go(name)`, one `Loader` for the current screen (Now Playing is created once and kept: it is hidden, not destroyed, when another screen shows), `Keys.onUpPressed` on the content scope → `topBar.focusCurrent()`; Down from the bar → the item that had focus before if still visible, else `focusDefault()`. `goBack()` keeps today's overlay order, then asks the screen's `handleBack()`, then applies `Nav.back`. When `Nav.validScreen(screen, app.lyricsEnabled, app.visualizerEnabled) !== screen`, go to it (Review Focus 3). `Binding`s copy `app.accent1/2` into `Theme.a1/a2`. Setup needed → `go("settings")` as today. Volume and media shortcuts unchanged. `app.pulseVisible` is bound to `screen === "now"` and app active; `app.vizVisible` is set by the Visualizer screen.

- [ ] **Step 1: Failing tests.** `test_nav_js.py` (same loader as `tests/test_typing_js.py`): `tabs(true,true)` is the five in order; `tabs(false,true)` lacks `lyrics`; `validScreen("lyrics", false, true) == "now"`; `validScreen("settings", false, false) == "settings"`; `back("guests","queue") == "queue"`; `back("search","search") == "now"`; `back("now","now") == "exit"`. `test_topbar_qml.py`: after `focusCurrent()` with `screen: "queue"` the focused item is the Queue tab; Right ×3 reaches the chip and Return emits `go("speakers")`; Left at the first tab stays; Down emits `leaveDown`; with `guestMode: true` the Guest chip is not in the focus order; a 60-character `speakerName` keeps the bar within 1920 px (Review Focus 5).
- [ ] **Step 2:** Run both; expect failures.
- [ ] **Step 3:** Implement. Pages keep their content for now (restyled in later tasks) but must load inside the shell.
- [ ] **Step 4:** Tests pass. `scripts/dev-deploy.sh --run`; on the TV check: every tab opens, Up/Down between bar and content, Back order, typing on Now Playing opens Search, QR card appears with guest mode and opens Guests, `~/couchside-run.log` has no QML errors.
- [ ] **Step 5:** Commit `feat: top bar with tabs; screens swap under it instead of stacking`.

### Task 6: Now Playing

**Files:** Modify `NowPlayingPage.qml`, `ArtBackground.qml`, `UpNext.qml`, `TrackProgress.qml`, `VolumePopup.qml`, `BeatGlow.qml`.

Layout at 1080p (mockup lines 62-133): blurred art + gradient `rgba(7,7,11,.35) → .98`; art 560 px, radius 28, centred at top 150, `scale: 1 + 0.028 * app.audioPulse` when the visualizer is on; block 1180 px wide at bottom 50: title 84/800, "artist — album" 38, guest credit 28 in `a1` when `app.nowPlayingCredit`, progress (8 px bar, gradient fill, 28 px times), control row: shuffle, repeat | previous, play/pause, next | volume, party. Default focus play/pause; Left/Right along the row; Right from party or Up from the row's right half → Up Next card. Up Next: top 124, right 48, width 432, panel fill, rows 28/24 px, 4 rows (3 while the QR card shows, placed below it); it shows `app.queueRows` after the current item, falling back to `nextTitle`; focusable, OK → `go("queue")`. Party button: `app.visualizerMode = "party"` then `go("visualizer")`. Status text (`app.statusText`) top-left under the bar in `Theme.warn`. Nothing playing: art placeholder, title "Nothing playing", controls still focusable (Review Focus 4). Lyrics are no longer shown on this screen: remove the lyrics layout and its hold timer.

- [ ] **Step 1:** Implement the layout.
- [ ] **Step 2:** Full suite passes (fix harness tests touching `UpNext`).
- [ ] **Step 3:** Deploy; on the TV compare with the mockup at the same size; check focus path across all seven controls and the Up Next card, volume popup, nothing-playing state, QR card overlap.
- [ ] **Step 4:** Commit `feat: Now Playing in the Jukebox layout`.

### Task 7: Search and Queue

**Files:** Modify `LibraryPage.qml`, `QueuePage.qml`, `MediaCardItem.qml`.

Search (mockup lines 135-160): padding 148/150/50; field with 42 px icon, 44 px text, radius 24; rows via `ListRow` (thumb 104, title 42, subtitle 28, `hint: "PLAY"`). Keep section labels per kind, recents when the field is empty, busy and error text, the action sheet on OK, and `typeInto(text)`. Queue: heading "Queue" + count, same rows, current item marked with an `a1` bar, "added by" credit as a badge, existing sheet actions, focus kept on the same song when rows change (existing `takeRows`).

- [ ] **Step 1:** Implement.
- [ ] **Step 2:** Full suite passes.
- [ ] **Step 3:** Deploy; check search by typing and by on-screen keyboard, each action in the sheet, reorder/remove in Queue, empty queue text.
- [ ] **Step 4:** Commit `feat: Search and Queue in the Jukebox style`.

### Task 8: Lyrics screen

**Files:** Create `LyricsPage.qml`. Modify `LyricsView.qml`, `tests/test_lyrics_view_qml.py`.

`LyricsView` gains `property string look: "inline"`; with `look: "stage"` it renders the mockup (lines 162-176): line height 120, current line 92 px/800 in `a1`, distance 1: 48 px at 50 %, 2: 42 px at 28 %, further: 38 px at 12 %, eased 550 ms scroll, top/bottom fade (opacity gradient items, not a shader mask). The `size` setting scales those sizes by 0.85 / 1 / 1.15. The translation line sits under each line at 60 % of its size. `LyricsPage` owns the position timer (250 ms, only while visible and playing), shows the stage view, or, without lyrics, the artwork at 420 px with "No lyrics for this song" / "Looking for lyrics…" while `app.lyricsPending`.

- [ ] **Step 1: Failing test** in `test_lyrics_view_qml.py`: with `look: "stage"` and position inside line 3, the item for line 3 has `font.pixelSize == 92` and colour `Theme.a1`, line 4 has `48`; with `size: "large"` line 3 has `round(92*1.15)`.
- [ ] **Step 2:** Run it; expect failure. **Step 3:** Implement. **Step 4:** Suite passes.
- [ ] **Step 5:** Deploy; check a synced song, an unsynced one, a song without lyrics, translation on.
- [ ] **Step 6:** Commit `feat: full-screen Lyrics tab`.

### Task 9: Visualizer screen

**Files:** Create `VisualizerPage.qml`, `viz.js`, `tests/test_viz_js.py`. Modify `EdgeLights.qml` (unchanged behaviour, new parent). Delete `PartyView.qml` after moving its content.

**Interfaces — Produces:** `viz.js` (`.pragma library`): `radial(ctx, W, H, a, st)`, `flow(ctx, W, H, a, st)`, `bars(ctx, W, H, a, st)` where `a = {energy, beat, level, bars}` and `st` is a mutable state object (`{t, dt, spin, rings, prevBeat, c1, c2}`, colours as `{r,g,b}`); `frame(energy, beat, intensity, bars)` → `a` with `beat *= intensity` and `level = min(1.4, beat * (0.5 + energy * 0.6))`. Ported from the mockup's `vizRadial`, `vizFlow`, `vizBars`; `flow` replaces `shadowBlur` with a second wider, fainter stroke.

Screen: a `Canvas` 1280×720 scaled to fill, repainted by a 33 ms `Timer` that runs only while the screen is visible, the app is active and the mode is not `party`; sets `app.vizVisible`. Mode pill at the bottom: Radial Pulse, Flow Lines, Bars, Party (active = gradient fill, dark text); Left/Right change `app.visualizerMode`. Top-left: BEAT chip (focused: Left/Right change `app.visualizerIntensity` by 0.05, shown as a gradient bar) and the source chip (`app.beatSourceLabel`, dot `a1` while listening; OK opens the sheet with `app.beatSources`, `checked` = current, callback `app.setBeatSource`). Party mode shows the former `PartyView` content (big lyrics or bouncing artwork, `EdgeLights` when `app.partyLights`). Controls and the top bar fade out after 4 s without a key and return on any key (the first key only reveals them). Nothing playing: the canvas idles on zero input with the text "Play something to see it move" (Review Focus 4).

- [ ] **Step 1: Failing test** `test_viz_js.py`: load `viz.js` in a `QJSEngine` with a fake `ctx` that counts calls; `frame(0.5, 1, 2, null).beat == 2` and `.level == min(1.4, 2*0.8)`; each of `radial`, `flow`, `bars` runs with 64 bars and with all-zero input without throwing and calls `fill` or `stroke` at least once; `radial` adds a ring when beat crosses 0.55 upward and none while it stays above.
- [ ] **Step 2:** Run; expect failure. **Step 3:** Implement. **Step 4:** Suite passes.
- [ ] **Step 5:** Deploy; with music playing check all four modes, intensity, source list (switch to the microphone and back), auto-hide, Back. Measure: `ssh mediac@192.168.30.153 'top -b -n 3 -d 2 | grep -i -E "python|couchside"'` on each mode; record the numbers in the commit body. If a mode holds more than about half a core, lower its canvas size before moving on.
- [ ] **Step 6:** Commit `feat: Visualizer tab with Radial, Flow, Bars and Party; beat source and intensity`.

### Task 10: Speakers, Guests, Settings, overlays

**Files:** Modify `SpeakersPage.qml`, `GroupEditor.qml`, `GuestsPage.qml`, `SetupPage.qml`, `PairingOverlay.qml`, `AdminCodeOverlay.qml`, `VolumePopup.qml`, `Main.qml` (exit dialog). Delete `PageBackground.qml` if unused.

Same content and behaviour; new surfaces, rows, focus ring, type sizes. Guests gets a first row "Guest mode: On — turn off". Settings changes:
- "This speaker → Audio output": value `app.audioOutputLabel`; OK opens the sheet with `app.audioOutputs` (sections, `checked`), callback `app.setAudioOutput`.
- Category "Party and visualizer" renamed "Visualizer": Beat pulse (existing), Beat source (`app.beatSourceLabel`, sheet with `app.beatSources`), Beat intensity (Left/Right ±0.05, OK cycles 0.5/1/1.5/2), Party lights (existing).
- New category "Look": Colours (`app.accents` in a sheet; each row shows its two colours as dots).
- `app.loadAudioDevices()` is called when Settings opens, as today.

- [ ] **Step 1:** Implement. **Step 2:** Suite passes.
- [ ] **Step 3:** Deploy; walk every Settings row with the remote; pick an HDMI output and confirm music moves to it (`pactl list short sink-inputs` shows Sendspin on that sink) and the visualizer still reacts; pick a direct device and confirm it plays; return to Default. Check group create/edit, transfer queue, guest promote/kick/reset, admin code, pairing PIN (`pairing` overlay), exit confirm.
- [ ] **Step 4:** Commit `feat: Speakers, Guests, Settings and overlays in the Jukebox style; output and beat-source pickers; colour presets`.

### Task 11: Guest page colours, docs, screenshots

**Files:** Modify `src/couchside/web/guest.html` (CSS colours only: background `#07070b`, accents teal/pink, same structure), `tests/test_guest_page.py` if it asserts colours, `README.md` (new navigation, the two audio settings, Colours), `flatpak/io.github.shreyasajj.Couchside.metainfo.xml` (release note). Move `Bigscreen Jukebox.dc.html` and `support.js` to `docs/design/`. Add `docs/screenshots/jukebox/*.jpg` for the nine screens.

- [ ] **Step 1:** Make the changes. **Step 2:** Suite passes. **Step 3:** Open the guest page from a phone via the QR on the TV; add a song.
- [ ] **Step 4:** Go through the spec's feature inventory line by line on the TV; fix anything unreachable.
- [ ] **Step 5:** Commit `docs: Jukebox UI screenshots, README, guest page colours`.
