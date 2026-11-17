# Jukebox look for Couchside: design

Date: 2026-11-15. Reference mockup: `Bigscreen Jukebox.dc.html` (+ `support.js`, its
design-tool runtime) in the repo root, to be moved to `docs/design/`.

## Intent

Give the app the look of the "Bigscreen Jukebox" mockup: a top tab bar, teal-to-pink
accents on near-black, a centred artwork with a floating Up Next card, full-screen lyrics,
and a full-screen visualizer with three drawing modes. Every feature the app has today
stays. Two settings are added or improved: which audio output Sendspin plays through, and
where the visualizer listens for beats.

## Goals

- The four mockup screens (Now Playing, Search, Lyrics, Visualizer) match the mockup in
  layout, colour, type weight and focus style.
- Screens the mockup doesn't have (Queue, Speakers, Guests, Settings, overlays) are
  restyled in the same language and reachable from the top bar.
- No feature is lost (inventory below). Everything works with D-pad, OK and Back.
- Still a Flatpak with the bundled Sendspin daemon; no new runtime dependencies beyond what
  the beat-source list needs.
- The visualizer is usable on a Raspberry Pi and never costs CPU when it is not on screen.

## Non-goals

- No backend behaviour changes other than: spectrum bars, beat-source choice, beat
  intensity, accent choice, output picker as a list.
- No change to the guest phone page's layout or its API (colours only).
- No touch or mouse polish beyond what QML gives for free.

## Anti-goals

- Focus that gets lost or lands on a hidden control.
- A visualizer that makes the rest of the app stutter, or keeps the audio device open
  when nothing shows it.
- A feature that exists today but can't be reached in the new layout.

## Approaches

1. **Rebuild the screens in QML on the existing controller (chosen).** The mockup is the
   visual reference; the `app` controller object, focus rules and tests carry over. Keeps
   the Flatpak as it is and keeps rendering on Qt's scene graph, which the Pi handles.
2. **Show the HTML mockup itself in a Qt WebEngine view and wire it to the backend.** Looks
   identical on day one, but adds a browser engine to the Pi, needs every feature the
   mockup lacks to be written again in HTML, and needs a second remote-focus system.
   Dropped.
3. **Recolour only (change `Theme.qml`).** Cheap, but doesn't give the tab bar, the centred
   Now Playing or the visualizer, which are the point. Dropped.

Picked by Claude after the user asked whether it was doable; the user chose "keep every
feature, restyled" for the screens the mockup lacks.

## Look

All values at 1080p, multiplied by `u` as today. `Theme.qml` becomes:

- Background `#07070b`; accents `a1 #00e0c6` (teal) and `a2 #ff3da6` (pink); the
  gradient `a1 → a2` is used for the active tab underline, progress and volume fill, the
  play button, the active visualizer mode and the wordmark.
- Surfaces: white at 4-6 % with a 1-2 px white 6-12 % border; panels over artwork are
  `rgba(10,10,16,.5)` with a border (blur behind only where it is cheap; otherwise a more
  opaque fill).
- Focus: a 3 px `a1` ring with a soft `a1` glow; focused list rows also get the
  teal-to-pink tinted fill and scale 1.012, as in the mockup's search rows. This replaces
  today's "focused control is white".
- Type: Noto Sans, weights 500-800. Sizes from the mockup (title 84, subtitle 38, row
  title 42, tab 30), **but nothing the viewer has to read goes below 28 px** (project
  rule). The mockup's 18-23 px text (Up Next rows, chips) is raised to 28/24, so the Up
  Next card shows 4 rows (3 with the QR up) instead of 5. *Claude's call.*
- Accent pairs: a "Colours" setting with the mockup's four presets (teal/pink default).
  *Claude's call.*
- Wordmark: gradient square + "Couchside" (the app keeps its name and app id). *Claude's
  call; the mockup says "Bigscreen Jukebox".*

## Structure

`Main.qml` stops using a pushed page stack for the main screens. A persistent **top bar**
sits over a content area that swaps screens:

```
[■ Couchside]   Now Playing  Search  Queue  Lyrics  Visualizer   [● Playing on Living Room ▾] [Guest] [⚙]
```

- Tabs: Now Playing, Search, Queue, Lyrics, Visualizer. Lyrics is hidden when "Show
  lyrics" is off; Visualizer when the visualizer setting is off.
- "Playing on …" chip → Speakers screen (list, groups, transfer). Shown on every screen.
- Guest button: guest mode off → OK turns it on. Guest mode on → the white QR card
  (QR, caption, URL) takes the button's place in the top-right on every screen, and is
  focusable: OK opens the Guests screen (guest list, admin code, promote/kick/reset, turn
  guest mode off).
- Gear → Settings.
- Speakers, Guests and Settings are screens without a tab; Back returns to the tab you
  came from.

Remote rules:

- Up from the top row of any screen moves to the top bar, onto the current tab. Left/Right
  move along the bar, OK activates, Down returns to the content where it was.
- Back: closes an overlay, else leaves a non-tab screen, else goes to Now Playing, else
  (on Now Playing) the exit confirm. Media and volume keys work everywhere, as today.
- Typing letters on Now Playing still opens Search with them.
- Pairing PIN, admin code, action sheet, group editor, toast and exit confirm stay
  overlays, restyled.

## Screens

**Now Playing.** Blurred artwork background with the mockup's dark gradient. Sharp
artwork (560 px, radius 28) centred, scaling slightly with the beat. Below: title,
"artist — album", guest credit when there is one, progress with elapsed/total, then one
focusable control row: shuffle, repeat · previous, play/pause (116 px gradient circle),
next · volume, party. Default focus is play/pause. Up Next card top-right (below the QR
card when it is up); it is focusable and OK opens Queue. Status/reconnect text top-left
under the bar. The mockup's "Left/Right = previous/next" is not used, because the row has
more than three controls. *Claude's call.*

**Search.** Big search field, then rows as in the mockup (104 px thumb, 42 px title,
28 px subtitle, PLAY hint on the focused row). Keeps: recently played and recently added
when the field is empty, kinds (tracks, albums, artists, playlists, radio) as section
labels, and the Play now / Play next / Add to queue sheet on OK-hold or the row's menu
action exactly as today.

**Queue.** Same row style; current item marked; "added by" credit; reorder, remove,
play-next via the existing sheet.

**Lyrics.** The mockup's full-screen scroller: current line 92 px in `a1`, neighbours
fading out, top/bottom fade mask. Keeps romanized/original/English-only, the translation
line under each line, and the size setting (scales the mockup's sizes). No lyrics: a
quiet "No lyrics for this song" with the artwork. Lyrics no longer take over Now Playing.

**Visualizer.** Full-screen, modes in a pill at the bottom: Radial Pulse, Flow Lines,
Bars (ported from the mockup's drawing code) and **Party** (today's party mode: big
lyrics or artwork, edge lights). Top-left: BEAT intensity (Left/Right when focused,
saved) and a chip showing the beat source; OK on the chip opens the source list. The bar
and controls fade out after a few seconds without a key press and return on any key. The
party button on Now Playing jumps here in Party mode.

**Speakers, Guests, Settings.** Same content and behaviour as today in the new
row/panel style. Settings keeps its two panes and gains the items below.

## New and changed settings

- **This speaker → Audio output**: opens a list instead of cycling. Checked on the TV
  (2026-11-15): `sendspin audio-devices list` gives raw ALSA devices (`hw:0,3` …) that
  bypass PipeWire, so nothing can listen to them, plus `pulse`/`default`. `pactl` works
  inside the sandbox and lists the real outputs. So the list is:
  - "Default";
  - each PipeWire output by its description (stored as `sink:<name>`; the daemon runs
    with `--audio-device pulse` and `PULSE_SINK=<name>`);
  - under "Direct (visualizer can't listen)": the ALSA devices, as today.
  A saved device that is unplugged stays in the list. Saving restarts the daemon as today.
- **Visualizer → Beat source**: a list of
  - "What this TV is playing" (default): the monitor of the output chosen above when it
    is a PipeWire output, else of the default output;
  - each output's monitor, by name;
  - each input (microphone, line-in).
  Stored as `visualizer_source` (None = automatic). Changing it reopens the stream. A
  source that has gone away falls back to automatic and says so in a toast.
- **Visualizer → Beat intensity** (0-2.4, `visualizer_intensity`), also adjustable on the
  Visualizer screen.
- **Colours** (`accent`): one of four presets.
- Existing "Beat pulse" and "Party lights" stay.

## Backend changes

- `BeatDetector.feed` also produces 64 log-spaced bars (0..1.15) from the FFT it already
  runs; `AudioPulse` keeps the latest. The controller exposes `spectrum` (list) and
  updates it, with level and beat, about 30 times a second **only while the Visualizer
  screen is in front**; elsewhere the existing 20 Hz stepped pulse is unchanged.
- `open_monitor_stream` takes the chosen source instead of always `@DEFAULT_MONITOR@`;
  a function lists sources (name, description, monitor or input).
- Controller: `audioDevices` (list) + `setAudioDevice(name)`, `beatSources` +
  `setBeatSource(id)` + `beatSourceLabel`, `visualizerIntensity`, `visualizerMode`,
  `accent`. `cycleAudioDevice` is removed with its row.
- `AppSettings`: `visualizer_source`, `visualizer_intensity`, `visualizer_mode`, `accent`.

## Constraints

- PySide6 from the PySide BaseApp, KDE runtime 6.11, QML + Kirigami window; no WebEngine.
- Visualizer drawing must hold up on a Pi: draw at no more than 1280×720 and scale up,
  cap at 30 fps, stop the timer when the screen is not in front or the app is not active.
  Avoid full-screen blur effects that redraw every frame.
- Flatpak has `--socket=pulseaudio` only. Listing sources must work inside the sandbox.
- Commits and PR text must not mention Claude Code.

## Feature inventory (must all still be reachable)

Play/pause, next, previous, shuffle, repeat, volume (popup + keys), progress; artwork
background; Up Next; guest credit; status and reconnect text; setup/first-run token
entry; pairing PIN; search over five kinds; recents; play now/next/add; queue view,
reorder, remove; speaker list, switch, groups create/edit, transfer queue; lyrics with
language, translation, size; party mode with edge lights; beat pulse on artwork; guest
mode toggle, QR, caption, public URL, quotas, cooldown; guest list, admin code, promote,
revoke, kick, reset; player name, audio output, sync delay; app and Sendspin versions and
update button; toast; exit confirm; media keys.

## Order of work

1. Theme, shared controls (tab bar, rows, pills, focus ring), new `Main.qml` shell.
2. Now Playing.
3. Search, Queue, Lyrics.
4. Spectrum + beat source + intensity in the backend; Visualizer screen.
5. Speakers, Guests, Settings (with the two list pickers and Colours), overlays.
6. Guest phone page colours, README, new screenshots, mockup moved to `docs/design/`.

Each step keeps the test suite green; QML harness tests are extended for the top bar's
focus rules and the pickers.

## Left to the builder

- How the Visualizer is drawn (Canvas at reduced size, or scene-graph items/shaders),
  within the constraints above.
- Sources and outputs are listed with `pactl -f json list sources|sinks` (present in the
  runtime; verified on the TV). When `pactl` is missing or fails, both lists show only
  "Default"/"What this TV is playing" and the direct devices.
- Exact sizes for the screens the mockup doesn't show.
