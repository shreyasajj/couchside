# Phase 5: Guest Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Party guests scan a QR code on the TV, enter a name on a phone page served by Couchside, and can search, add songs, use their skips and boosts within host-set limits; the TV shows who added each song.

**Architecture:** `core/guests.py` (Qt-free) holds the session (token, rules, guests by device id, who added which queue item) and the policy (can add / skip / boost). `core/guest_server.py` is an aiohttp web app embedded in the app's event loop (qasync) serving the phone page and a small JSON + WebSocket API; it calls MA through the existing connection. The controller turns guest mode on/off, exposes the QR matrix, the guest URL and credits; QML draws the QR top-right on Now Playing and "added by" credits.

**Spec:** [design](../specs/2026-11-10-couchside-design.md) (guest reachability, public URL, QR caption, skip/boost rules, attribution, guest server), [Agents.md](../../../Agents.md) "Guest mode".

**Branch:** `phase5-guest-mode` from `main`.

## Decisions (design + my calls)

- Server on port **8765**, all interfaces, plain HTTP (TLS is a reverse proxy's job). Relative paths only so it works behind the owner's proxy; live updates over WebSocket with automatic fallback to polling every 3 s.
- QR encodes `<base>/g/<token>`: base = Settings "Guest page public URL" when set, else `http://<this TV's LAN IP>:8765`. The token is 16 random URL-safe characters, new every time guest mode is turned on; old links stop working.
- Guest identity: a random device id kept in the phone's localStorage plus a display name (1–24 chars). Same device = same guest across reloads while guest mode stays on.
- Guests add **tracks** only (albums/playlists would bypass the per-guest limit). Search results for guests: tracks.
- Rules (host settings, defaults): skips per guest **3**, boosts per guest **2**, max songs per guest waiting in the queue **3**, cooldown between adds **0 s** (off).
- Skip: ends the current song, whoever added it; costs one skip. Boost: moves one of the guest's own waiting songs to play next (newest boost wins: `move_next`); costs one boost.
- Attribution: after an add, the queue item that appeared for that URI is mapped to the guest; kept in memory for the guest session (lost on restart; design accepts this).
- Guests can't change volume, shuffle, reorder, remove others' songs or switch speakers (no such endpoints).
- TV: QR top-right of Now Playing (≈ 200 px at 1080p, white quiet zone) with the host caption (Settings, default "Scan to add songs", at most 2 lines); "Added by <name>" pill under the title / in the lyrics header; Queue rows show "Added by <name>". Settings → Guest mode section: Guest mode on/off, QR caption, Guest page public URL, the four limits (cycling presets).
- Guest mode is off at launch until turned on (a party is a deliberate act); turning it on starts the server and shows the QR.

## Global Constraints

- Nothing a guest sends can crash the app or reach MA without passing the rules; every endpoint validates the token, device id, name and input sizes; errors are JSON `{error}` with 4xx.
- The guest page works on any phone browser without a build step: one HTML file, inline CSS/JS, no external requests.
- TV UX rules from earlier phases (D-pad only, focus never lost, ≥ 28 px text).
- Commit messages never mention Claude Code; they end with the Co-Authored-By line.

## Tasks

1. **Guest session and rules** — `core/guests.py`: `GuestRules`, `Guest`, `GuestSession(rules, token=None)` with `join(device_id, name)`, `check_add(guest, waiting_count, now)`, `use_skip`, `use_boost(guest, item_id)`, `credit(item_id, guest)`, `added_by(item_id)`, `waiting_count(guest, upcoming_ids)`, `new_token()`. Tests for every rule and limit, name/device validation, token rotation.
2. **Guest actions against MA** — in `core/guests.py` or `core/guest_actions.py`: `add_track(client, queue_id, session, guest, uri)` (snapshot ids → play_media ADD → attribute new item), `skip(client, queue_id, session, guest)`, `boost(client, queue_id, session, guest, item_id)`, `guest_state(...)` (now playing, upcoming with owner/mine flags, the guest's remaining skips/boosts and limits). Tests with fakes.
3. **Web server** — `core/guest_server.py` (aiohttp): `GET /g/<token>` (page), `POST /api/join`, `GET /api/state`, `GET /api/search?q=`, `POST /api/add`, `POST /api/skip`, `POST /api/boost`, `GET /api/ws` (state pushes); start/stop; `lan_ip()`. Tests with aiohttp's test client: wrong token 403, join validation, add/skip/boost happy paths and limit errors, search returns tracks only, input size caps.
4. **Guest page** — `src/couchside/web/guest.html`: name step, now playing, search + Add, "Your songs" with Boost, Skip button with counts, error toasts; WebSocket with polling fallback; relative URLs; works on a narrow phone screen. Checked by requests from the Mac (curl/python) and served-file test.
5. **TV side** — controller: `guestMode` (toggle starts/stops server, rotates token), `guestUrl`, `qrRows` (list of strings of 0/1), `qrCaption`, `guestPublicUrl`, rule settings with cycle slots, `creditFor(itemId)` / `nowPlayingCredit`; settings fields; QML: `QrCode.qml` (draws modules), Now Playing QR + caption + credit pill, Queue "Added by", Settings Guest section. Tests for controller properties. TV check with a simulated guest (python client from the Mac on the LAN): join, add, see credit on TV, boost, skip, limits; QR scanned by a phone if the owner tries it.
6. **Packaging + docs** — `segno` in pyproject + `flatpak/requirements.txt` + regenerated `python-deps.json`; package data for the web page; README guest section (how to start, limits, reverse-proxy note incl. WebSocket upgrades), API notes; PR, CI, merge.
