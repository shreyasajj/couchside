# Couchside — design

A TV-first Music Assistant app for Plasma Bigscreen. The base spec is
[Agents.md](../../../Agents.md); everything in it stands. This document records
the intent behind it, what was decided in conversation, what was found on the
real hardware, and which calls were made on the owner's behalf.

## Intent

The owner already tried this once ("Bigscreen Jukebox", an AppImage on the TV
box). It "wasn't working well, and the UI looked clunky." So success is:

1. **It works reliably** — connects, reconnects, plays, never crashes or loses
   focus with a remote.
2. **It looks polished** on a TV from the couch.

Anti-goals: a UI that looks like a desktop app stretched onto a TV; flaky
behaviour that makes the host reach for a phone instead.

The old Jukebox is left untouched. Couchside is a separate app with its own
launcher tile.

## Hardware and environment (verified 2026-11-10)

- **TV box:** mini PC, x86_64, KDE neon User Edition 24.04, Qt 6.11.1,
  Plasma Bigscreen shell (`org.kde.plasma.bigscreen`), Kirigami and
  Bigscreen QML modules present, PipeWire running (`pw-cat`, `wpctl`
  available). Reachable at `ssh mediac@192.168.30.153` (key auth works).
  Python 3.12.3. PySide6 6.11.1 from neon packages (only `qtcore` installed
  today). `uv` and `sendspin` not installed.
- **Music Assistant:** server 2.10.9, schema 65, Home Assistant add-on on a
  Raspberry Pi (Home Assistant Yellow, CM4) at `http://192.168.30.3:8095`.
  Advertised over mDNS as `_mass._tcp` (`mass.local:8095`); TXT records include
  `server_id`, `server_version`, `base_url`. Remote access is enabled, so
  token auth is expected to be required.
- **Dev machine:** macOS, no Qt/Kirigami. Pure-Python logic is unit-tested
  here; anything touching QML, Sendspin or PipeWire is tested on the TV box
  over SSH (deploy via rsync).

## Decided by the owner

- **Backend: Python + PySide6.** Must use the distro PySide6 (neon apt
  packages) so it matches the system Qt that Kirigami is built against. Never
  pip-install PySide6.
- **Now Playing = "Layout B, lyrics-forward"** (mockup approved):
  - Blurred full-screen artwork background, darkened toward the bottom.
  - Top-left: small sharp artwork (~10% of width), title, "artist · album",
    and an "added by <guest>" pill when a guest queued it.
  - Lyrics fill the middle, left-aligned: the current line is **very large**
    (~6% of screen width, ≈115px at 1080p, bold, soft shadow), the next line
    medium (~3.4%), the one after and the previous line smaller and faded.
    Smooth auto-scroll between lines.
  - **No-lyrics fallback:** big artwork left (~33% width), large title
    (~4.6% width), artist and album below, credit pill.
  - Bottom bar: progress line, elapsed / −remaining, then shuffle, previous,
    play/pause (larger, filled), next, repeat, volume. Clear focus ring
    (bright blue, offset) on the focused control.
  - Guest-mode QR code in the top-right.
- **QR caption:** host-editable text shown under the QR code (Settings),
  default "Scan to add songs". Kept short; wraps to at most two lines.

- **Guest reachability:** guests either share the TV's LAN, or the owner puts
  a reverse proxy (HTTPS) in front of the TV box. So Settings has an optional
  **"Guest page public URL"** (e.g. `https://party.example.com`). When set,
  the QR encodes that base URL; when empty, it encodes the LAN URL
  `http://<tv-ip>:<port>`. The app itself only serves plain HTTP; TLS is the
  proxy's job. The guest page must work behind a proxy: relative paths only,
  no hard-coded host, and its live updates must survive a proxy (use
  WebSocket with automatic fallback to polling, and document that the proxy
  must pass WebSocket upgrades).
- **Testing on the live system is allowed:** the real MA server and speakers
  may be used for development and tests. Any speaker groups created during
  testing are removed afterwards and existing groups restored. The owner will
  create an MA access token and hand it over for phase 1.
- **Skip and boost rules:**
  - A guest skip ends whatever is currently playing, whoever added it. It
    costs one skip.
  - A boost moves one of the guest's *own* queued songs to play next. It
    goes ahead of any earlier boosts, so the newest boost wins. It costs one
    boost.
- **Player auto-select** matches only on the Sendspin client id, never on
  name, so a leftover player (e.g. from the old Jukebox) or another speaker
  with the same name can't be picked by mistake.

- **Packaging: Flatpak, Flathub-acceptable, and the same Flatpak is what the
  owner installs on the TV box.** This replaces Agents.md's `uv tool install`
  + systemd user service:
  - Sendspin is **bundled inside** the Flatpak (built from source in the
    manifest, with its audio deps). No sandbox escapes
    (`flatpak-spawn --host` / `org.freedesktop.Flatpak` talk-name are not
    allowed).
  - Sendspin runs as a **separate background process** inside the sandbox,
    started at login via the Background portal (autostart). It keeps running
    when the UI is closed, so the TV stays a speaker in MA.
  - Sendspin config lives in the sandbox:
    `~/.var/app/<app-id>/config/sendspin/`. Preserved across updates.
  - **Updates (phase 7):** Settings shows bundled vs. latest Sendspin version
    (latest from PyPI/GitHub). The Update button updates the whole Couchside
    Flatpak through the Flatpak portal's self-update (`CreateUpdateMonitor` /
    `Update`), then restarts the Sendspin process. New Sendspin versions ship
    as Couchside releases.
  - Install script shrinks to: install the Flatpak, grant/confirm background
    autostart. Dev iteration on the TV box over SSH still allowed outside the
    Flatpak (venv against system PySide6) for speed.
  - Flathub extras: AppStream metainfo, icon, licence, vendored Python deps.
  - App id must be on a namespace the owner controls (e.g.
    `io.github.<user>.Couchside`). Owner to supply later; not blocking
    phase 1 (use a placeholder until then).
- **Sendspin settings screen:** the TV Settings has a Sendspin section to set
  up the bundled client: player name, audio output device (from PipeWire),
  sync/static delay, and any other options the Sendspin client exposes.
  Changes write the Sendspin config and restart the Sendspin process.

## Calls made for the owner (changeable)

- **Name:** "Couchside" (from the project folder). App id
  `org.couchside.app`; `.desktop` file installed to
  `~/.local/share/applications/` so it appears as a Bigscreen tile.
- **Sendspin player name:** "Living Room TV" (editable in Settings; change
  rewrites the Sendspin config and restarts the service).
- **Git:** repo initialised in this folder. Commit messages and PR
  descriptions must not mention Claude Code (owner's rule in Agents.md).
- **Process:** the 8 phases in Agents.md, in order. Each phase ends with a
  test on the TV box and a short summary to the owner before the next starts.
  The implementation plan details phase 1 fully; later phases are outlined
  and re-planned when reached, using what earlier phases taught (several of
  them depend on the "verify early" items below).

## Architecture (builder's latitude, with these constraints)

- **Runtime:** a venv created with `--system-site-packages` (so it sees the
  neon PySide6), with pure-Python deps installed into it: the official
  `music-assistant-client`, `zeroconf`, `aiohttp` (guest web server),
  `qrcode`, later `numpy`. Apt deps installed by the install script:
  `python3-pyside6.qtquick`, `.qtqml`, `.qtgui`, `.qtnetwork`, `.qtsvg` and
  whatever else QML needs.
- **Async:** Music Assistant client and aiohttp are asyncio-based; Qt needs its
  own loop. Use one integrated loop (qasync, or PySide6.QtAsyncio if it proves
  stable on 6.11) — the builder chooses after a quick spike; no threads
  shuttling state between loops.
- **Layering:** a Python core (MA connection, player/queue state, guest/admin
  rules, lyrics, settings) with no Qt imports where practical, so it is
  testable on macOS. A thin Qt layer exposes it to QML as models and
  properties. QML + Kirigami for the UI.
- **Settings** stored under `~/.config/couchside/` (token kept in a file with
  0600 permissions). `~/.config/sendspin/` is never overwritten wholesale —
  only the specific keys the app owns are edited.
- **Connection:** mDNS discovery by default, manual address override, token
  auth. Exponential-backoff reconnect with an on-screen status; the UI stays
  usable (shows "Reconnecting…") with no server.
- **Player auto-select:** on connect, select the MA player that is this
  machine's Sendspin client, matched by Sendspin client id (see above). The
  builder confirms which MA player field carries that id.
- **Guest attribution:** MA's queue doesn't record who added an item, so the
  app keeps a map of queue item id → guest name for the current guest-mode
  session. It is lost if the app restarts; acceptable.
- **Guest web server:** embedded in the app, on a fixed LAN port (builder
  picks one that doesn't clash, e.g. 8765). Plain HTML/JS mobile page, no
  build step. Guest identity is a random device id kept in the phone's
  browser storage; admin status attaches to that device id until revoked or
  guest mode ends.

## Things to verify early (spec may be wrong)

- MA 2.10 auth flow over the WebSocket and how tokens are created (owner will
  create one in the MA web UI; the app can't).
- Exact `sendspin` CLI daemon flags, config file location/format, and how the
  client identifies itself to MA.
- Whether MA metadata carries synced lyrics in 2.10, and in what form.
- Whether MA has a pairing PIN flow for Sendspin players at all.
- How Bigscreen delivers remote/CEC keys to apps (likely as standard Qt key
  events via the Bigscreen input handler).

Record any differences in the README's "API notes" section, as Agents.md asks.

## Out of scope for now

- Home Assistant entities (Agents.md: not in phase 1; owner may ask later).
- Touching or removing the old Bigscreen Jukebox.
