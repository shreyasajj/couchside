# Build Prompt: "Bigscreen Music" — a Music Assistant app for Plasma Bigscreen

## Role and goal
You are a senior Linux/Qt developer. Build a TV-first music app for **KDE Plasma Bigscreen** that controls **Music Assistant (MA)** and plays audio locally through a **Sendspin** client running on the same machine. It must be fully usable with a TV remote from 10 feet away, and support a QR-code guest mode so party guests can add songs from their phones.

Work in phases (below). Finish, test, and summarize each phase before starting the next. Ask me before making any architecture decision that isn't covered here.

## Environment and stack
- Target: Plasma Bigscreen (KDE Plasma 6, Qt 6, KDE Frameworks 6) on x86_64 or Raspberry Pi.
- UI: QML + Kirigami, following Plasma Bigscreen conventions (Mycroft/Bigscreen-style focus navigation). App must register as a launcher tile in the Bigscreen home screen via a `.desktop` file.
- Backend logic: C++ or Python (PySide6) — recommend one and justify it before starting.
- Music Assistant: connect to the MA server WebSocket API (default port 8095). Support token-based auth. Server address and token configurable in Settings, with mDNS auto-discovery as the default.
- Sendspin: the open-source synchronized audio protocol native to Music Assistant (spec at github.com/Sendspin/spec). Use the official Python CLI client (`sendspin`, installable with `uv tool install sendspin`) running in daemon mode as a systemd user service.
- Home Assistant: optional. Only needed if I later want HA entities on screen; don't build it in phase 1.

## Sendspin client setup
- Provide an install script that installs the `sendspin` client, configures it in daemon mode with a friendly player name (e.g. "Living Room TV"), and enables a systemd user service so it starts on boot.
- The app checks for Sendspin client updates (on launch and daily), shows the installed/available version in Settings, and can run the upgrade + service restart with one button. Existing settings in `~/.config/sendspin/` must be preserved.
- On launch, the app auto-selects this machine's Sendspin player as the active MA player.
- If MA requires pairing, display the pairing PIN in large text on screen.

## Core features

**Now Playing screen (home screen of the app)**
- Full-screen blurred album artwork as the background; large sharp artwork, title, artist, and album in the foreground.
- Synced lyrics layered on top of the blurred background, current line highlighted and large, auto-scrolling. Use lyrics from MA's metadata if available, otherwise fetch time-synced lyrics from LRCLIB. Hide the lyrics layer gracefully when none are found.
- Bottom control bar: previous, play/pause, next, shuffle, repeat, volume, progress bar with elapsed/remaining time.

**Speaker / group picker**
- List all MA players and groups, show which is active and what each is playing.
- Switch the controlled player, create/edit groups (sync multiple speakers), and transfer the current queue to another player.

**Search and browse**
- Search across tracks, albums, artists, playlists, and radio using MA's search. On-screen keyboard friendly; also support voice/remote text input if Bigscreen provides it.
- Actions on any result: Play now, Play next, Add to queue.
- Recently played and recently added sections, plus the current queue view with reorder/remove.

## Guest mode
- A "Guest Mode" toggle in the app. When on, show a QR code in the top-right corner of the Now Playing screen (small but scannable from a couch).
- The QR opens a mobile web page served by the app itself on the LAN (embedded HTTP server). The QR contains a session token that rotates whenever guest mode is restarted.
- Guests enter a display name, then can: search, add songs to the queue, use their **skips**, and use their **boosts** (a boost moves their song to play next).
- Host settings (on the TV): skips per guest, boosts per guest, max songs per guest in queue, and optional cooldown between adds.
- Show who added each song in the queue view and as a small credit on Now Playing.
- Guests cannot change volume, shuffle, reorder, remove others' songs, or switch speakers.

## Admin access
- Admins are separate from the guest QR. The host grants admin from the TV, using either a one-time 6-digit code shown on screen or by promoting a connected guest from a guest list.
- Admins get: unlimited skips, reorder/shuffle/remove anything in the queue, volume, speaker/group switching, and the ability to kick a guest or reset their quotas.
- Host can revoke admin at any time. Admin status persists across reconnects from the same device until revoked or guest mode ends.

## TV / 10-foot UX requirements
- Every action reachable with D-pad + OK + Back only. Clear, high-contrast focus ring on the focused element; focus never gets lost.
- Minimum body text ~28px at 1080p; titles larger. Large hit targets, generous spacing, no hover-only UI.
- Back always goes to the previous screen; Back on Now Playing exits after a confirm.
- Map media keys (play/pause, next, previous, volume) from remotes and HDMI-CEC.
- Handle disconnects gracefully: show reconnect status, never crash on a missing MA server.

## Phases
1. **Foundation:** project scaffold, Bigscreen launcher tile, MA connection + discovery, Sendspin install script and service, player auto-select, basic play/pause/next.
2. **Now Playing:** artwork background, metadata, bottom control bar, progress, remote navigation polish.
3. **Search, queue, recents, speaker/group picker.**
4. **Lyrics:** synced lyrics layer with LRCLIB fallback.
5. **Guest mode:** embedded web server, QR, guest page, skip/boost quotas, host settings.
6. **Admin access:** codes, promotion, revocation, admin tools.
7. **Sendspin auto-update** from within the app.
8. **Visualizer (stretch):** a subtle pulse behind the artwork that reacts to the beat. Capture audio from the local PipeWire output, do lightweight FFT/onset detection, and keep CPU use low enough for a Raspberry Pi. Must be toggleable in Settings.

## Deliverables
- Source code with a clear README (install, configure, run, update).
- Install script for dependencies, the Sendspin client, and the systemd service.
- A Settings screen covering: MA server/token, player name, guest quotas, admin management, lyrics on/off, visualizer on/off.
- Brief notes on anything in the Sendspin or MA APIs that turned out to be unstable or different from this spec.

## Extra
please dont use claude code in description in the pr or in the commit history