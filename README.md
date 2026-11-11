# Couchside

A TV-first [Music Assistant](https://music-assistant.io) app for **KDE Plasma Bigscreen**.
It turns the TV into a Music Assistant speaker (through a bundled
[Sendspin](https://www.sendspin-audio.com) client) and a remote-friendly player.

Status: **Phase 6**: connect, bundled speaker, Now Playing (blurred artwork, progress,
shuffle, repeat, volume, synced lyrics), search with recently played/added, the queue,
the speaker and group picker, guest mode and admin access. Sendspin updates and the
visualizer follow in later phases (see [Agents.md](Agents.md) and the [design](docs/superpowers/specs/2026-11-10-couchside-design.md)).

## Install (on the Bigscreen TV)

Couchside ships as a Flatpak. Everything installs per-user; no `sudo` needed.

```bash
git clone <this repo> ~/couchside
~/couchside/scripts/install.sh
```

The script installs the build tools it needs from Flathub (`org.flatpak.Builder`,
`org.kde.Sdk//6.11`, `io.qt.PySide.BaseApp//6.11`), builds the app and installs it.
A **Couchside** tile appears on the Bigscreen home screen.

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

Remote: Left/Right move along the control bar (shuffle, previous, play/pause, next,
repeat, volume, settings), OK activates, Back goes back (on Now Playing it asks before
exiting). On the volume button, OK opens a volume bar: Left/Right change it by 5, OK or
Back closes it. Media keys (play/pause, next, previous) work anywhere.

**Lyrics.** When a song has time-synced lyrics, Now Playing switches to the lyrics
layout: centered, the line being sung large, the next one smaller, scrolling with the
music. Songs without synced lyrics keep the big-artwork layout. Lyrics come from the
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

**Guest mode.** Settings → Guest mode → On shows a QR code (with your caption) in the
top-right of Now Playing. Guests scan it, enter a name, and can search and add songs,
skip the playing song and boost one of their own songs to play next, within the limits
you set (skips and boosts per guest, songs waiting per guest, wait between adds). Their
songs play first come, first served, right after the current song (ahead of Music
Assistant's autoplay suggestions); the TV shows "Added by <name>". Guests can't change
volume, shuffle, reorder, remove others' songs or switch speakers. Turning guest mode off
and on makes a new QR code (old links stop working); guest mode is off when the app
starts.

**Admins.** While guest mode is on, Settings → Guest mode → **Guests and admins** lists
the guests who joined. Make someone an admin either way:

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

The guest page is served by Couchside on port **8765** of this TV (plain HTTP on your
network). For HTTPS or access from outside, put a reverse proxy in front of it and set
**Guest page public URL**; the proxy must pass WebSocket upgrades (`/g/<token>/api/ws`)
— if it doesn't, phones fall back to polling every 3 s.

The buttons at the right of the bar open:

- **Search**: OK on the search box starts typing (Bigscreen's on-screen keyboard opens);
  its Enter, or Back, runs the search and jumps to the results. Up/Down move between
  rows (Tracks, Albums, Artists, Playlists, Radio), Left/Right along a row, OK offers
  Play now / Play next / Add to queue. With nothing typed it shows Recently played and
  Recently added.
- **Queue**: what is still to play. OK on a song: Play this now, Play next, Move up/down,
  Remove.
- **Speakers**: every speaker and group, which one you control, what each is playing.
  OK on a speaker: Control this speaker, Move the queue here, Sync with the controlled
  speaker / Stop syncing; groups also have Edit members and Delete group. "New group"
  makes a synced group from two or more speakers. Couchside always starts on this TV.

Volume keys: Plasma uses the remote's volume keys for the system volume, so they
don't reach Couchside. Use the on-screen volume bar (it sets this TV's volume in Music
Assistant), or unbind Plasma's "Increase/Decrease Volume" shortcuts in System Settings →
Shortcuts to let Couchside handle them.

## Update

```bash
cd ~/couchside && git pull && scripts/install.sh
```

Settings, the token and Sendspin's identity are kept. (Phase 7 adds an in-app update button.)

## Develop

- **Unit tests** (any machine; PySide6-Essentials comes with the `test` extra for the
  controller tests):
  `python3 -m venv .venv && .venv/bin/pip install -e '.[test]' && .venv/bin/pytest`
- **On the TV:** `scripts/dev-deploy.sh --run` syncs this checkout to the TV over
  SSH (`COUCHSIDE_TV`, default `mediac@192.168.30.153`), rebuilds the Flatpak
  (only the app module rebuilds) and starts it on screen.
- **Python deps** for the Flatpak are pinned in `flatpak/python-deps.json`.
  Regenerate after changing `flatpak/requirements.txt`:
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
- **Translation APIs.** Google: `translate.googleapis.com/translate_a/single?client=gtx`
  (unofficial). DeepL: `POST /v2/translate` on `api-free.deepl.com` for keys ending in
  `:fx`, `api.deepl.com` otherwise. LibreTranslate: `POST <url>/translate` with a list `q`.
  One request per song; a result with the wrong number of lines is discarded.
- **Flatpak instead of `uv` + systemd** (owner's decision, see design doc):
  Sendspin is bundled and autostarted through the Background portal.
