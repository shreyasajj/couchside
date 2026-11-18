# Couchside

A TV-first [Music Assistant](https://music-assistant.io) app for **KDE Plasma Bigscreen**.
It turns the TV into a Music Assistant speaker (through a bundled
[Sendspin](https://www.sendspin-audio.com) client) and a remote-friendly player.

Status: **Phase 8** (all phases): connect, bundled speaker, Now Playing (blurred artwork,
progress, shuffle, repeat, volume, synced lyrics, a beat pulse), party mode, search with
recently played/added, the queue, the speaker and group picker, guest mode, admin access,
in-app updates and Sendspin settings (see [Agents.md](Agents.md) and the [design](docs/superpowers/specs/2026-11-10-couchside-design.md)).

## Install (on the Bigscreen TV)

Couchside ships as a Flatpak, published as a signed repo on GitHub Pages. Everything
installs per-user; no `sudo` needed.

```bash
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user https://shreyasajj.github.io/couchside/couchside.flatpakref
```

A **Couchside** tile appears on the Bigscreen home screen. Installed this way, the app
updates itself from Settings (see [Update](#update)). x86_64 only for now.

To build it yourself instead: `git clone <this repo> ~/couchside && ~/couchside/scripts/install.sh`
(installs the build tools from Flathub, builds and installs; such a build doesn't get
in-app updates).

On first launch Couchside:

- starts its bundled Sendspin player ("Living Room TV") and asks the desktop to
  start it at every login, so the TV stays available in Music Assistant even when
  the app is closed;
- shows the **Connect to Music Assistant** page.

## Configure

1. In the Music Assistant web app, open **Settings → your profile → Long-lived
   access tokens** and create a token.
2. On the TV, enter it on the Connect page (OK opens the on-screen keyboard).
   Leave **Server address** empty to find the server automatically (mDNS), or type
   an address such as `192.168.30.3` (`http://` and port `8095` are added).

If Music Assistant asks to pair the TV, the pairing code is shown in large text
on screen. Enter it in Music Assistant.

Settings live in the Flatpak's sandbox:

| What | Where |
|------|-------|
| App settings | `~/.var/app/io.github.shreyasajj.Couchside/config/couchside/settings.json` |
| MA token (0600) | `~/.var/app/io.github.shreyasajj.Couchside/config/couchside/token` |
| Sendspin settings + identity | `~/.var/app/io.github.shreyasajj.Couchside/config/sendspin/` |
| Sendspin log | `~/.var/app/io.github.shreyasajj.Couchside/.local/state/couchside/sendspin.log` |
| Login autostart | `~/.config/autostart/io.github.shreyasajj.Couchside.desktop` (created by the Background portal) |

## Run

From the Couchside tile, or `flatpak run io.github.shreyasajj.Couchside`.

**Getting around.** A bar across the top of every screen has the tabs — Now Playing,
Search, Queue — and, on the right, the speaker in use (opens
Speakers), Guest, and Settings. Up from the top of any screen reaches the bar; Left/Right
move along it, OK opens, Down goes back to where you were. Back goes to Now Playing (from
the Visualizer, Speakers, Guests or Settings: to the tab you came from); on Now Playing it asks before
exiting.

**Now Playing.** The cover, the song, its progress, and one row of controls: shuffle,
repeat, previous, play/pause, next, volume, lyrics, visualizer. Left/Right move along the row, OK
activates. On the volume button, OK opens a volume bar: Left/Right change it by 5, OK or
Back closes it. **Up Next** (top right) lists the next songs; OK on it opens the Queue.
Media keys (play/pause, next, previous) work anywhere.

**Lyrics.** The Lyrics button on Now Playing moves the song into the top-left corner
(a small cover with the title and artist, floating gently) and puts its time-synced lyrics
in the middle: the line being sung large and in colour, the others fading away above and
below, scrolling with the music. Up Next stays on the right and the controls (volume too)
stay at the bottom. The visualizer moves behind the words, dimmed, with its edge lights at
full strength (Settings → Lyrics → Visualizer behind the lyrics; off shows the blurred
cover). The button again brings the cover back; the choice is remembered. Songs without
synced lyrics say so. Lyrics come from the
track's own metadata in Music Assistant when present, otherwise from
[LRCLIB](https://lrclib.net) (Couchside sends the song's title, first artist, album and
length — nothing else).

Settings → **Lyrics**:

| Setting | Choices (default first) |
|---|---|
| Show lyrics | On / Off |
| Size | Medium / Large / Small |
| Language | **Romanized** (other scripts — Gurmukhi, Devanagari, Cyrillic, Hangul… — written in English letters) / **Original** (as sung) / **English only** (songs not sung in English show the artwork) |
| English underneath | Off / On — a translation under each line, only for songs not in English |
| Translation service | **Google** (no setup; unofficial, may stop working) / **DeepL** (free API key from deepl.com/pro-api, stored like the MA token) / **LibreTranslate** (your own server's address) |

With English underneath on, the playing song's lyrics are sent to the chosen service.
Romanization is rule-based and approximate (Japanese kanji get Chinese readings).

**Guest mode.** **Guest** in the top bar (or Settings → Guest mode → On) shows a QR code
on a white card (with your caption) in the top-right corner of every screen. OK on the
card opens the guest list, where guest mode is also turned off. Guests scan it, enter a name, and can search and add songs,
skip the playing song and boost one of their own songs to play next, within the limits
you set (skips and boosts per guest, songs waiting per guest, wait between adds). Their
songs play first come, first served, right after the current song (ahead of Music
Assistant's autoplay suggestions); the TV shows "Added by <name>". Guests can't change
volume, shuffle, reorder, remove others' songs or switch speakers. Turning guest mode off
and on makes a new QR code (old links stop working); guest mode is off when the app
starts.

**Admins.** While guest mode is on, the QR card (or Settings → Guest mode → **Guests and
admins**) opens the list of guests who joined. Make someone an admin either way:

- **Admin code:** "Show an admin code" puts a 6-digit code on the TV. On their phone the
  guest taps "Have an admin code from the host?" and enters it. It works once, for 10
  minutes; Back cancels it. Each phone gets 3 tries, and 20 wrong tries in all cancel it.
- **Promote:** OK on a guest → Make admin.

Admins see an Admin panel on the guest page: skip without limits, add without limits,
move any song up or down, play it next, remove it, shuffle, volume, and which speaker
plays ("Control" switches the speaker the TV controls; "Move music" moves the queue
there). They can give a guest their skips and boosts back, or remove a guest from the
party, but can't change other admins. From the TV you can do all of that to anyone and
remove admin at any time. Admin belongs to the phone (it survives reloads) until you
remove it or guest mode ends. A removed guest can't rejoin from that phone until guest mode
restarts (on your network, not from a private tab either); their songs stay in the queue.
Behind a reverse proxy every phone shares the proxy's address, so a determined guest can
rejoin from a new browser there.

The guest page is served by Couchside on port **8780** of this TV (plain HTTP on your
network); change it in Settings → Guests → **Guest page port** if something else uses it.
(It used to be 8765, which Bigscreen Bridge now uses.) For HTTPS or access from outside, put a reverse proxy in front of it and set
**Guest page public URL**; the proxy must pass WebSocket upgrades (`/g/<token>/api/ws`)
— if it doesn't, phones fall back to polling every 3 s.

The other screens:

- **Search**: OK on the search box starts typing (Bigscreen's on-screen keyboard opens);
  its Enter, or Back, runs the search and jumps to the results: a row of covers per kind
  (Tracks, Albums, Artists, Playlists, Radio). Up/Down change row, Left/Right move along
  it, OK offers Play now / Play
  next / Add to queue. With nothing typed it shows Recently played and Recently added.
- **Queue**: what is still to play. OK on a song: Play this now, Play next, Move up/down,
  Remove.
- **Speakers**: every speaker and group, which one you control, what each is playing.
  OK on a speaker: Control this speaker, Move the queue here, Sync with the controlled
  speaker / Stop syncing; groups also have Edit members and Delete group. "New group"
  makes a synced group from two or more speakers. Couchside always starts on this TV.

**Visualizer.** The sparkle button on Now Playing opens the Visualizer, which draws the
music full-screen. Left/Right on the row at
the bottom change the picture: **Radial Pulse** (turning spokes that send a ring out on
every beat), **Flow Lines**, **Bars** (the spectrum), **Edge Lights** (the spectrum growing in from
all four edges of the screen over a rim of light; each piece of the edge glows as bright as
its own part of the music is loud, so bass lights up one corner and voices and cymbals
light up further along; the colours run round the frame once every eight beats, so they speed up and slow down with the song's
tempo, and LED strips that follow the screen move with it), and **Party**. Top left: what it listens to (OK
picks another source), **BEAT**, how hard the picture hits on each beat (Left/Right), and
**Colours**: the theme's two colours, the whole rainbow, or a new colour on every beat,
and **Edge lights** (OK switches): the Edge Lights border over Radial, Flow and Bars too. After a few seconds without a key the controls and the top bar fade away;
any key brings them back.

**Party** mode: laid out like Now Playing with its lyrics on, without the controls. The
song floats small in the top-left corner (once the controls fade away), the lyrics fill the
middle and bounce with the music over a glow, and Up Next sits on the right. Songs without
lyrics show their cover bouncing instead. **Party lights** (Settings → Visualizer, on by
default) put the Edge Lights round it, so LED strips that follow the screen dance with the
music.

Settings → **Visualizer**:

| Setting | What it does |
|---|---|
| Beat pulse on Now Playing | The cover and a glow behind it move with the beat (on by default) |
| Beat source | **What this TV is playing** (default: the output chosen under This speaker, or the default output), one specific output, or an input such as a microphone |
| Beat intensity | 0–2.4, how hard the Visualizer hits on a beat |
| Colours | Theme colours, Rainbow, or Changes on the beat |
| Edge lights on every picture | The Edge Lights border over the other pictures too (off by default) |
| Party lights | The Edge Lights round Party mode |

Couchside listens through PipeWire; nothing is recorded or sent anywhere. It listens only
while Now Playing (with the beat pulse on, or with the lyrics over the visualizer) or the
Visualizer is on screen and music plays. A chosen source that is unplugged falls back to what this TV plays.

**Audio output** (Settings → This speaker): where this TV's music comes out. The list
shows **Default**, then every PipeWire output by name (HDMI, analog, …), then the
hardware devices under "Direct (visualizer can't listen)" — those bypass PipeWire, so the
visualizer hears nothing through them. Changing it restarts the speaker for a moment.

**Crossfade** (Settings → This speaker, read from Music Assistant): **Crossfade** on or
off for the speaker in use, its **style** (Music Assistant's default, Standard, or Smart:
beat-matched, picking its own length) and the standard crossfade's **length** (1–15 s,
Left/Right). The length is Music Assistant's own setting for every speaker (the number
Home Assistant shows); the rows hide when Music Assistant can't be reached.

**When something breaks.** A **Something's wrong** button appears next to the name in the
top bar when this TV's speaker keeps stopping or isn't running, when Music Assistant can't
be reached or refuses the token, or when this TV's speaker is missing from Music
Assistant (the last few only after they last 15 seconds, so a short reconnect doesn't
count). OK on it opens **Logs**: what is wrong, **Restart this TV's speaker**, and the
recent speaker (Sendspin) and Couchside logs (Up/Down scroll). Logs are also in Settings →
This speaker. The app also replaces a speaker supervisor left running from an older
version of the app (it lives on across app updates), so a fix in an update takes effect.

**Colours** (Settings → Look): four colour pairs for focus, progress and the visualizer.

**Keyboard on the remote:** just type. On Now Playing, typing opens Search with what you
typed; on Search it goes into the search box; in Settings into the highlighted text box.

Volume keys: Plasma uses the remote's volume keys for the system volume, so they
don't reach Couchside. Use the on-screen volume bar (it sets this TV's volume in Music
Assistant), or unbind Plasma's "Increase/Decrease Volume" shortcuts in System Settings →
Shortcuts to let Couchside handle them.

## Update

Settings → **Updates** shows this build's version and whether a newer one is published
(Flatpak checks in the background). OK on **Update available** installs it, then
restarts Sendspin and the app. The **Sendspin** row shows the bundled Sendspin version
and the newest on PyPI (checked at launch and daily); new Sendspin versions arrive as
Couchside updates. Settings, the token and Sendspin's identity are kept.

Every change merged to `main` is published by the Release workflow
(`.github/workflows/release.yml`): it builds the Flatpak, signs it with the key in the
`FLATPAK_GPG_PRIVATE_KEY` secret and deploys the repo to GitHub Pages. Dependabot bumps
Sendspin and the other bundled packages in `flatpak/requirements.txt`; those PRs merge
themselves when CI passes, which publishes a release. The signing key's backup lives
outside the repo (`~/.config/couchside-release/` on the owner's Mac); losing it means
TVs must re-add the remote with a new key.

**Sendspin speaker** settings: player name (how the TV appears in Music Assistant),
audio output (Default or a device Sendspin reports) and sync delay (to line this TV up
with other speakers). Changes restart the speaker within a couple of seconds.

## Develop

`flatpak run io.github.shreyasajj.Couchside --screen=queue` starts on a screen (`now`,
`search`, `queue`, `visualizer`, `speakers`, `guests`, `settings`, `logs`).
`COUCHSIDE_SHOTS=<dir> pytest tests/test_shell_qml.py` loads the whole UI offscreen and
saves a picture of every screen (blur and glow effects don't draw offscreen). The design
mockup the look follows is in `docs/design/`.

- **Unit tests** (any machine; PySide6-Essentials comes with the `test` extra for the
  controller tests):
  `python3 -m venv .venv && .venv/bin/pip install -e '.[test]' && .venv/bin/pytest`
- **On the TV:** `scripts/dev-deploy.sh --run` syncs this checkout to the TV over
  SSH (`COUCHSIDE_TV`, default `mediac@192.168.30.153`), rebuilds the Flatpak
  (only the app module rebuilds) and starts it on screen.
- **Python deps** for the Flatpak: `flatpak/requirements.in` lists what Couchside uses
  directly; `flatpak/requirements.txt` is the full pinned tree compiled from it with
  pip-compile inside `org.kde.Sdk//6.11` (Python 3.13), which Dependabot keeps up to date
  as a whole. The file list `flatpak/python-deps.json` is generated from it at build time
  (CI, release, install.sh):
  `flatpak run --share=network --filesystem="$PWD" --command=python3 org.kde.Sdk//6.11 flatpak/gen-python-deps.py`

Layout: `src/couchside/core` (Qt-free logic: settings, discovery, MA connection,
player selection), `src/couchside/sendspin` (bundled player helpers),
`src/couchside/ui` (Qt bridge + QML/Kirigami).

## API notes (where reality differed from the spec)

- **Music Assistant token is mandatory.** MA 2.10.9 (schema 65) refuses
  unauthenticated clients (`AuthenticationRequired`); `music-assistant-client`
  sends the token with an `auth` command after connecting.
- **Sendspin client id is a public key.** Since pairing support, Sendspin's
  `client_id` is the base64url public key derived from `identity-daemon.json` in its
  settings dir, not the player name. Couchside reads it there to find its own player
  in MA and matches on ids only (`player_id`, or an `output_protocols[]` id).
  Verified on MA 2.10.9: the Sendspin client is wrapped in a `universal_player`
  (e.g. `upa0dd8b65`) whose `output_protocols[0]` id is the Sendspin client id, so
  the match goes through `output_protocols`.
- **Pause reads as idle.** After pausing a Sendspin player, MA reports
  `playback_state` = `idle`, not `paused`. Play/pause from idle resumes the queue,
  so the button still works; the UI treats anything but `playing` as "show Play".
- **Pairing code is only logged.** `sendspin daemon` writes
  `Pairing required: enter pairing code … on the server.` to its log and nothing
  else; there is no "paired" message. Couchside follows the log and hides the code
  once its player appears in MA.
- **`sendspin daemon` arg order:** the app name must follow `sendspin` directly
  (`sendspin daemon --name X`). The package has no `__main__`, so Couchside calls
  `sendspin.cli:main`.
- **Default port clash.** Sendspin 9.1 listens on 8928 by default. Couchside's copy
  uses **8937** (`sendspin_port` in settings) so it can run beside another
  Sendspin install on the same machine.
- **MPRIS bus name** is `org.mpris.MediaPlayer2.Sendspin.instance<pid>`, hence the
  `--own-name=org.mpris.MediaPlayer2.Sendspin.*` Flatpak permission.
- **Image proxy sizes.** MA 2.10.9's `/imageproxy/…?size=N` only accepts 256, 512 and
  1024 and answers `400 Bad Request` for anything else; Couchside rounds up.
- **Album palette.** `player.current_media.palette` carries colours extracted from the
  artwork (`background_dark`, `accent`, …); Now Playing tints its background with it.
- **Position.** The queue's `elapsed_time` (+ `elapsed_time_last_updated`, server
  epoch seconds) is more current than the player's; Couchside uses the queue's and
  falls back to `current_media` for sources without an MA queue. Progress ticks locally
  between updates, so the TV and server clocks should both use NTP.
- **Recently added** (`music/recently_added_tracks`) needs schema 101; on MA 2.10.9
  Couchside lists library tracks sorted by `timestamp_added_desc` instead.
- **Groups.** Speakers report `can_group_with`; syncing is `players/set_members` on the
  leader. Named groups use the `sync_group` provider (`players/create_group_player`),
  deleted with `players/remove_group_player`.
- **Event volume.** While music plays MA sends `queue_updated`/`player_updated` several
  times a second; Couchside only rebuilds the queue and speaker lists when their
  contents change, so the remote's focus stays put.
- **Bigscreen keyboard.** It opens on any focused text field and takes the arrow keys,
  and it swallows the first key press after it hides; Couchside only starts editing on
  OK. Run with `--debug-focus` to log focus changes when tracing remote navigation.
- **Lyrics.** `metadata/get_track_lyrics` needs schema 101; on 2.10.9 Couchside reads
  `metadata.lrc_lyrics` of the track (`music/item_by_uri`) and otherwise asks LRCLIB
  (`/api/get` with the first artist — MA joins artists with `/` — then `/api/search` by
  title, matched on length within 3 s). Plain (unsynced) lyrics are not shown.
- **Guest songs and "play next".** MA queues items carry no marker for autoplay
  ("don't stop the music") additions, so guests' songs are added as `next` and moved
  below the other guests' waiting songs; MA inserts `next` after the song already
  buffered for gapless playback, so one song may play first.
- **Volume handed to another control.** When a player's `volume_control` in MA points
  at another entity (as on the test TV), `players/cmd/volume_set` succeeds but the level
  doesn't change; the TV's volume bar and the admins' volume buttons both depend on it.
- **Self-update.** Flatpak's portal (`org.freedesktop.portal.Flatpak`, version 6 on the
  TV) gives an update monitor (`CreateUpdateMonitor`, `UpdateAvailable`, `Progress`,
  `Update`) and `Spawn` with the latest-version flag, so the sandboxed app can update and
  relaunch itself. It only works for an app installed from a remote that gets new
  commits, hence the published repo; a locally built install never sees updates. The
  portal checks the remote on its own schedule.
- **Sendspin options.** `sendspin daemon` has `--audio-device` (index, name prefix or ALSA
  name), `--output-delay-ms`, `--hardware-volume`, `--audio-format` and hooks; Couchside
  exposes the output (by name, since indexes move) and the delay.
- **Beat pulse.** The Flatpak's PulseAudio socket can record the default sink's monitor
  (`PULSE_SOURCE=@DEFAULT_MONITOR@` with PortAudio's `pulse` device), muted or not. An
  FFT of 1024 samples 21 times a second takes ~20 µs each. What cost CPU was QML: 60 fps
  animations redrew the whole 4K screen; the pulse is now computed in Python in 0.05 steps
  at most 20 times a second and QML just shows it.
- **Remote keys.** Kirigami's PageRow binds `StandardKey.Back` (the remote's Back key);
  with a second shortcut on the same key Qt rotates presses between them, so Couchside
  disables Kirigami's. A Python application-wide event filter crashed PySide (6.11) on
  the TV, so that route is not used.
- **Translation APIs.** Google: `translate.googleapis.com/translate_a/single?client=gtx`
  (unofficial). DeepL: `POST /v2/translate` on `api-free.deepl.com` for keys ending in
  `:fx`, `api.deepl.com` otherwise. LibreTranslate: `POST <url>/translate` with a list `q`.
  One request per song; a result with the wrong number of lines is discarded.
- **Flatpak instead of `uv` + systemd** (owner's decision, see design doc):
  Sendspin is bundled and autostarted through the Background portal.

### Bigscreen Bridge UI control

Couchside exposes a local, UI-only session-bus endpoint at
`io.github.shreyasajj.Couchside.Control`, path
`/io/github/shreyasajj/Couchside/Control`, method `Execute(JSON) → JSON`.
The Flatpak manifest grants ownership of that name only. No broad session-bus
permission is required. A D-Bus name lock keeps patched UI launches single-instance;
subsequent launches request focus on the existing UI before exiting.

Requests carry a unique `id` and a `command` (`get_state`, `focus`, `navigate`).
`focus` preserves the current UI. `navigate` accepts `content_type` and
`content_id`: `now_playing` with an empty ID, `search` with a query, or
`track`/`album`/`artist`/`playlist` with a matching Music Assistant URI, for example
`library://album/123`. Items are resolved through the connected MA client before
opening a detail page; navigation never starts playback. Use Music Assistant's
HA integration for playback. Unknown types, disconnected MA, missing content and
navigation failures return explicit errors. Responses echo the request ID;
repeated IDs return a bounded cached response and cannot change the request body.

`get_state` reports readiness, supported content types, MA playback ownership and
the local Sendspin player's MA ID. `view` records the most recent acknowledged
bridge navigation, not subsequent manual remote navigation. Closing the UI leaves
the separately supervised Sendspin process alone.

Local IPC trusts the logged-in Unix user. This endpoint has no remote JavaScript,
shell, URL navigation, token access or playback commands. Network access goes
through Bigscreen Bridge's authenticated API.
