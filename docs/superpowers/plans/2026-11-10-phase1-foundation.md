# Couchside Phase 1 (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Couchside Flatpak that appears as a Bigscreen tile, finds and logs in to Music Assistant, runs a bundled Sendspin daemon at login, auto-selects this TV's Sendspin player, shows the pairing PIN if one is needed, and offers play/pause, next and previous with a remote.

**Architecture:** A Qt-free Python core (`couchside/core/`, `couchside/sendspin/`) holds settings, discovery, the MA connection, player selection and Sendspin helpers; it is unit-tested on macOS. A thin Qt layer (`couchside/ui/`) runs the asyncio loop inside Qt via `qasync` and exposes one `AppController` QObject to QML/Kirigami. Sendspin runs as a separate process (`couchside-sendspin`) inside the same Flatpak, autostarted at login via the Background portal.

**Tech Stack:** Python ≥3.12, PySide6 6.11 (from `io.qt.PySide.BaseApp//6.11`), Kirigami (from `org.kde.Platform//6.11`), `music-assistant-client` 1.8.x, `zeroconf`, `qasync`, `sendspin` 9.1.x (+ `aiosendspin` 10.x), pytest + pytest-asyncio.

**Spec:** [docs/superpowers/specs/2026-11-10-couchside-design.md](../specs/2026-11-10-couchside-design.md), base spec [Agents.md](../../../Agents.md).

## Global Constraints

- App id placeholder: `io.github.shreyasajj.Couchside` (the owner's existing Flatpak `io.github.shreyasajj.StremioTV` uses this namespace; confirm with owner before any Flathub submission). Display name "Couchside".
- Default Sendspin player name: `Living Room TV`. Default QR caption: `Scan to add songs`.
- MA default port `8095`; mDNS type `_mass._tcp.local.`. MA server 2.10.9 / schema 65 **requires a token** (`AuthenticationRequired` without one — verified).
- Never pip-install PySide6. In the Flatpak it comes from the PySide BaseApp.
- No sandbox escapes: no `flatpak-spawn --host`, no `--talk-name=org.freedesktop.Flatpak`.
- Player auto-select matches on Sendspin client id only, never on name.
- The TV box has no sudo for us: everything installs `--user`.
- Commit messages and PR text must never mention "Claude Code".
- Body text ≥ 28px at 1080p; every control reachable by D-pad + OK + Back; visible focus ring.
- Never crash on a missing/unreachable MA server; show status and keep retrying.

## Review Focus

1. **MA server down or restarting mid-session** → status shows "Reconnecting…", retries with backoff (1s doubling, max 30s), recovers state without restarting the app. (Task 4 test `test_reconnects_after_drop`.)
2. **Wrong or revoked token** → status "Login failed — check token in Settings", no retry storm (retry only after token change). (Task 4 test `test_auth_failure_stops_retrying`.)
3. **Sendspin player not (yet) registered in MA** (first boot, daemon still starting, awaiting pairing) → app shows "Waiting for this TV's speaker…" and selects it the moment it appears, never falls back to another player. (Task 5 test `test_selects_when_player_appears_later`.)
4. **Corrupt or hand-edited settings / identity files** → defaults are used and the app starts; Sendspin's own files are never rewritten wholesale. (Task 2 `test_corrupt_settings_uses_defaults`, Task 3 `test_corrupt_identity_returns_none`.)
5. **Several MA servers or none on mDNS** → none: manual entry screen; several: first one stays selected but the list is shown in Settings. (Task 3 `test_discover_returns_all_servers`.)

---

## File Structure

```
pyproject.toml                       package metadata, deps, entry points, pytest config
src/couchside/__init__.py            __version__
src/couchside/core/paths.py          XDG config/state dirs (Flatpak-aware via env)
src/couchside/core/settings.py       AppSettings + token file
src/couchside/core/discovery.py      mDNS discovery of MA servers
src/couchside/core/connection.py     MA connection manager: auth, backoff, status
src/couchside/core/playback.py       player auto-select + transport commands
src/couchside/sendspin/identity.py   read Sendspin client id from identity file
src/couchside/sendspin/pairing.py    parse daemon log for pairing code / failures
src/couchside/sendspin/runner.py     `couchside-sendspin` entry point (runs daemon, logs to file)
src/couchside/sendspin/autostart.py  Background portal autostart request (D-Bus)
src/couchside/ui/app.py              `couchside` entry point: QGuiApplication + qasync + QML engine
src/couchside/ui/controller.py       AppController QObject (properties/slots for QML)
src/couchside/ui/qml/Main.qml        Kirigami.ApplicationWindow, page stack, key handling
src/couchside/ui/qml/HomePage.qml    status, title/artist, prev/play/next
src/couchside/ui/qml/SetupPage.qml   server URL + token entry (on-screen-keyboard friendly)
src/couchside/ui/qml/PairingOverlay.qml   large PIN display
src/couchside/ui/qml/FocusButton.qml big round button with focus ring
flatpak/io.github.shreyasajj.Couchside.yml          manifest
flatpak/io.github.shreyasajj.Couchside.desktop
flatpak/io.github.shreyasajj.Couchside.metainfo.xml
flatpak/io.github.shreyasajj.Couchside.svg
flatpak/python-deps.json             generated by flatpak-pip-generator
scripts/install.sh                   user-level install on the TV box
scripts/dev-deploy.sh                rsync to TV box + incremental flatpak build + run
tests/...                            one test file per core module
README.md                            install, configure, run, update, API notes
```

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `src/couchside/__init__.py`, `src/couchside/core/__init__.py`, `src/couchside/sendspin/__init__.py`, `src/couchside/ui/__init__.py`, `tests/test_package.py`
- Modify: `.gitignore` (add `build-dir/`, `.flatpak-builder/`, `repo/`, `*.flatpak`)

**Interfaces:**
- Produces: package `couchside` with `__version__ = "0.1.0"`; console scripts `couchside = couchside.ui.app:main`, `couchside-sendspin = couchside.sendspin.runner:main`.

- [ ] **Step 1: Write `tests/test_package.py`**: `test_version` asserts `couchside.__version__ == "0.1.0"`.
- [ ] **Step 2: Create a Mac dev venv** `python3 -m venv .venv && .venv/bin/pip install -e '.[test]'`. Runtime deps in pyproject: `music-assistant-client~=1.8`, `zeroconf>=0.136`, `qasync>=0.27`, `aiosendspin~=10.3`. `test` extra: `pytest`, `pytest-asyncio`. Do **not** list PySide6 or `sendspin` (sendspin is a Flatpak module; PySide6 comes from the BaseApp). pytest config: `asyncio_mode = "auto"`, `testpaths = ["tests"]`, src layout.
- [ ] **Step 3: Run** `.venv/bin/pytest -q` → `1 passed`.
- [ ] **Step 4: Commit** `chore: scaffold couchside package`.

### Task 2: Paths and settings

**Files:**
- Create: `src/couchside/core/paths.py`, `src/couchside/core/settings.py`, `tests/test_settings.py`

**Interfaces:**
- Produces:
  - `config_dir() -> Path` = `$XDG_CONFIG_HOME/couchside` (fallback `~/.config/couchside`); `state_dir() -> Path` = `$XDG_STATE_HOME/couchside` (fallback `~/.local/state/couchside`); `sendspin_settings_dir() -> Path` = `$XDG_CONFIG_HOME/sendspin` (fallback `~/.config/sendspin`). Inside the Flatpak, XDG vars point at `~/.var/app/<id>/…`, which satisfies the design's sandbox location.
  - `@dataclass AppSettings: server_url: str | None = None; player_name: str = "Living Room TV"; qr_caption: str = "Scan to add songs"; guest_public_url: str | None = None`
  - `load_settings(path: Path | None = None) -> AppSettings`, `save_settings(s: AppSettings, path: Path | None = None) -> None` (JSON, atomic write via temp file + `os.replace`).
  - `load_token(path: Path | None = None) -> str | None`, `save_token(token: str, path: Path | None = None) -> None` (file `config_dir()/token`, created with mode 0600, stripped).

- [ ] **Step 1: Write tests**: `test_defaults_when_missing` (fields equal the defaults above); `test_roundtrip`; `test_unknown_keys_ignored` (`{"server_url": "http://x:8095", "bogus": 1}` loads); `test_corrupt_settings_uses_defaults` (file content `"{not json"` → defaults, no exception); `test_token_file_is_0600` (`stat.S_IMODE(p.stat().st_mode) == 0o600`); `test_token_stripped` (`"  abc\n"` → `"abc"`); `test_xdg_paths` (monkeypatch `XDG_CONFIG_HOME=/tmp/x` → `config_dir() == Path("/tmp/x/couchside")`, `sendspin_settings_dir() == Path("/tmp/x/sendspin")`).
- [ ] **Step 2: Run** `pytest tests/test_settings.py -v` → fails on import.
- [ ] **Step 3: Implement** the interfaces above.
- [ ] **Step 4: Run** → all pass.
- [ ] **Step 5: Commit** `feat: settings and token storage`.

### Task 3: Discovery and Sendspin helpers (identity, pairing log)

**Files:**
- Create: `src/couchside/core/discovery.py`, `src/couchside/sendspin/identity.py`, `src/couchside/sendspin/pairing.py`, `tests/test_discovery.py`, `tests/test_sendspin_identity.py`, `tests/test_pairing.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) MassServer: server_id: str; name: str; base_url: str; version: str`
  - `parse_mass_service(properties: dict[bytes, bytes | None], addresses: list[str], port: int) -> MassServer | None` — `base_url` from the `base_url` TXT record if present, else `http://{addresses[0]}:{port}`; `None` if neither is usable.
  - `async discover_mass(timeout: float = 4.0) -> list[MassServer]` — zeroconf `AsyncZeroconf` + `AsyncServiceBrowser` on `_mass._tcp.local.`, de-duplicated by `server_id`.
  - `read_client_id(settings_dir: Path) -> str | None` — reads `identity-daemon.json` (`{"private_key": <b64url>}`), returns `aiosendspin.noise.Identity.from_private_bytes(b64url_decode(pk)).peer_id`; `None` if missing or invalid. Never writes.
  - `class PairingEvent(Enum): CODE, FAILED, STARTED`; `parse_log_line(line: str) -> tuple[PairingEvent, str] | None`. Patterns (from sendspin 9.1.0 `daemon.py`): `Pairing required: enter pairing code (?P<code>.+?) on the server\.` → `(CODE, code)`; `Pairing failed: (?P<reason>.+)` → `(FAILED, reason)`; `Starting Sendspin daemon: (?P<id>\S+)` → `(STARTED, id)`. The daemon never logs a "pairing done" line: the UI clears the PIN when the player appears in MA (Task 5).
  - `async tail_log(path: Path, on_event: Callable[[PairingEvent, str], None], poll: float = 0.5) -> None` — follows the file from its current end, handles truncation (size shrinks → reopen from 0) and the file not existing yet.

- [ ] **Step 1: Write tests**:
  - `test_parse_uses_base_url_txt`: properties from the real server (`server_id=9cc41ff7c04e48e6a502301970c5af11`, `server_version=2.10.9`, `base_url=http://192.168.30.3:8095`, `name=Music Assistant (d5369777-music-assistant)`), addresses `["10.0.0.9"]` → `base_url == "http://192.168.30.3:8095"`, `version == "2.10.9"`.
  - `test_parse_falls_back_to_address`: no `base_url` → `"http://10.0.0.9:8095"`.
  - `test_parse_returns_none_without_address_or_url`.
  - `test_discover_returns_all_servers`: feed two fake service infos with distinct ids plus a duplicate through the de-dup function (factor `_dedupe(servers: list[MassServer]) -> list[MassServer]`, keep first) → 2 servers.
  - `test_client_id_matches_identity`: `Identity.generate()`, write `{"private_key": b64url_encode(i.private_bytes)}` to `tmp/identity-daemon.json` → `read_client_id(tmp) == i.peer_id`.
  - `test_missing_identity_returns_none`, `test_corrupt_identity_returns_none` (file `"xx"`; also assert the file content is unchanged afterwards).
  - `test_parse_code_line`: `"INFO:sendspin.daemon.daemon:Pairing required: enter pairing code 123 456 on the server."` → `(CODE, "123 456")`; `test_parse_failed_line`; `test_parse_started_line`; `test_parse_other_line_none`.
  - `test_tail_reports_appended_lines` (write file, start tail, append a code line, event arrives within 2s); `test_tail_handles_truncation`.
- [ ] **Step 2: Run** → fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** all tests → pass. Then live check from the Mac: `.venv/bin/python -c "import asyncio; from couchside.core.discovery import discover_mass; print(asyncio.run(discover_mass()))"` → one server with `base_url='http://192.168.30.3:8095'`.
- [ ] **Step 5: Commit** `feat: MA discovery and Sendspin identity/pairing helpers`.

### Task 4: MA connection manager

**Files:**
- Create: `src/couchside/core/connection.py`, `tests/test_connection.py`

**Interfaces:**
- Consumes: `MassServer`, `discover_mass`, `load_token` (Tasks 2–3); `music_assistant_client.MusicAssistantClient(server_url, aiohttp_session, token=...)`, its `connect()`, `start_listening(init_ready)`, `subscribe(cb)`, and `music_assistant_client.exceptions` (`AuthenticationRequired`, plus whatever the client raises for a rejected token — check `exceptions.py` and the `auth.py` flow; record in README API notes).
- Produces:
  - `class ConnState(StrEnum): IDLE, DISCOVERING, CONNECTING, CONNECTED, RECONNECTING, AUTH_FAILED, NO_SERVER`
  - `class Connection`: `__init__(self, get_url: Callable[[], Awaitable[str | None]], get_token: Callable[[], str | None], client_factory: Callable[[str, str | None], ClientLike] = default_factory, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep)`; `state: ConnState`; `client: ClientLike | None` (live client when CONNECTED); `on_state(cb: Callable[[ConnState], None])`; `on_event(cb: Callable[[MassEvent], None])`; `async run() -> None` (loop forever); `async stop()`; `retry_now()` (wakes the loop, used when the token or URL changes).
  - Backoff: 1, 2, 4, 8, 16, 30, 30… seconds; reset to 1 after a successful connect. On auth failure → `AUTH_FAILED` and wait for `retry_now()` instead of retrying. `get_url` returning `None` → `NO_SERVER`, retry with backoff.
  - `ClientLike` is a `Protocol` with exactly the client methods used here and in Task 5, so tests use a fake.

- [ ] **Step 1: Write tests** with a `FakeClient` and a fake `sleep` that records delays:
  - `test_connects_and_reports_connected` (states `CONNECTING → CONNECTED`).
  - `test_backoff_sequence` (factory fails 7 times → recorded sleeps `[1, 2, 4, 8, 16, 30, 30]`).
  - `test_reconnects_after_drop` (listening ends with a connection error → `RECONNECTING`, then `CONNECTED` again; backoff restarts at 1).
  - `test_auth_failure_stops_retrying` (factory raises the auth error → `AUTH_FAILED`, factory called exactly once until `retry_now()`, then called again).
  - `test_no_server_state` (`get_url` returns `None` → `NO_SERVER`).
- [ ] **Step 2: Run** → fail.
- [ ] **Step 3: Implement.** Use one `aiohttp.ClientSession` per `Connection`.
- [ ] **Step 4: Run** → pass.
- [ ] **Step 5: Live check (needs the owner's token).** Ask the owner for the MA token (MA web UI → Settings → profile → long-lived token) if not yet given; save it with `save_token` on the Mac dev box only (never commit). Script in scratchpad connects via `Connection`, prints `CONNECTED`, the player list (`player_id`, `name`, `provider`, any field that looks like a Sendspin client id), then stops. Record which field holds the Sendspin client id in README API notes; Task 5 depends on it.
- [ ] **Step 6: Commit** `feat: MA connection manager with backoff and auth handling`.

### Task 5: Player auto-select and transport

**Files:**
- Create: `src/couchside/core/playback.py`, `tests/test_playback.py`

**Interfaces:**
- Consumes: `Connection` (Task 4), `read_client_id` (Task 3), the player field identified in Task 4 Step 5.
- Produces:
  - `find_local_player(players: Iterable[Player], client_id: str) -> Player | None` — exact match on that field only.
  - `@dataclass NowPlaying: title: str; artist: str; album: str; image_url: str | None; state: Literal["playing", "paused", "idle"]`
  - `class Playback`: `__init__(self, conn: Connection, get_client_id: Callable[[], str | None])`; `active_player_id: str | None`; `local_player_found: bool`; `now_playing: NowPlaying | None`; `on_change(cb: Callable[[], None])`; `handle_event(event)` (re-evaluates on player/queue added/updated/removed events and on (re)connect); `async play_pause()`, `async next()`, `async previous()` — all act on the active player's queue via `client.player_queues.play_pause/next/previous(queue_id)`; no-ops (no exception) when no player is active or the client is disconnected.
  - Selection rule: if a user-chosen player id exists (Phase 3; field present now, `None`) use it; else the local Sendspin player. Never any other player.

- [ ] **Step 1: Write tests** (fake players/queues):
  - `test_selects_local_player_by_client_id` (three players, one matching → selected).
  - `test_ignores_same_name_other_player` (another player named "Living Room TV" with a different id is not selected).
  - `test_selects_when_player_appears_later` (none at start → `local_player_found is False`; a player-added event → selected, `on_change` fired).
  - `test_transport_calls_active_queue` (`play_pause` → fake records `("play_pause", queue_id)`; same for next/previous).
  - `test_transport_noop_when_disconnected`.
  - `test_now_playing_from_queue` (fake queue's current item → `NowPlaying` fields).
- [ ] **Step 2: Run** → fail. **Step 3: Implement.** **Step 4: Run** → pass.
- [ ] **Step 5: Commit** `feat: local player auto-select and transport controls`.

### Task 6: Sendspin runner and login autostart

**Files:**
- Create: `src/couchside/sendspin/runner.py`, `src/couchside/sendspin/autostart.py`, `tests/test_runner.py`

**Interfaces:**
- Consumes: `load_settings`, `sendspin_settings_dir`, `state_dir` (Task 2).
- Produces:
  - `build_daemon_argv(settings: AppSettings, sendspin_dir: Path) -> list[str]` = `[sys.executable, "-m", "sendspin", "daemon", "--settings-dir", str(sendspin_dir), "--name", settings.player_name]`. (Explicit app name goes immediately after `sendspin`, per its README.) Other Sendspin options stay in its own `settings-daemon.json`; Phase 7's Sendspin settings screen edits individual keys there.
  - `log_path() -> Path` = `state_dir() / "sendspin.log"`.
  - `main() -> int` (`couchside-sendspin`): single-instance via `fcntl.flock` on `state_dir()/sendspin.lock` (second instance exits 0); truncates the log if > 1 MB; runs the daemon with stdout+stderr appended to the log; restarts it after 3s if it exits non-zero; exits when the daemon exits 0 or on SIGTERM (forwarding it).
  - `async request_autostart(enable: bool = True) -> bool` (`autostart.py`): calls `org.freedesktop.portal.Background.RequestBackground` on the session bus (`org.freedesktop.portal.Desktop`, `/org/freedesktop/portal/desktop`) with options `reason="Keep this TV available as a Music Assistant speaker"`, `autostart=enable`, `commandline=["couchside-sendspin"]`, `dbus-activatable=False`, and waits for the `Response` signal on the returned request handle. Use `QtDBus` (available in PySide6). Returns `True` if granted. Called by the UI on first launch (Task 7), and also starts `couchside-sendspin` immediately with `QProcess.startDetached` if it isn't running.

- [ ] **Step 1: Write tests**: `test_argv` (exact list above with name `Living Room TV`); `test_single_instance` (second `acquire_lock()` returns `False` while the first holds it); `test_log_truncated_when_large`. Portal code is tested live only.
- [ ] **Step 2: Run** → fail. **Step 3: Implement.** **Step 4: Run** → pass.
- [ ] **Step 5: Commit** `feat: sendspin runner with single-instance lock and login autostart`.

### Task 7: Qt bridge and TV UI

**Files:**
- Create: `src/couchside/ui/app.py`, `src/couchside/ui/controller.py`, `src/couchside/ui/qml/{Main,HomePage,SetupPage,PairingOverlay,FocusButton}.qml`

**Interfaces:**
- Consumes: everything from Tasks 2–6.
- Produces: `AppController(QObject)` registered as QML context property `app` with:
  - Properties (each with a NOTIFY signal): `connState: str`, `statusText: str`, `title: str`, `artist: str`, `album: str`, `artUrl: str`, `isPlaying: bool`, `hasLocalPlayer: bool`, `pairingCode: str` (empty = hidden), `serverUrl: str`, `hasToken: bool`.
  - Slots: `playPause()`, `next()`, `previous()`, `saveConnection(url: str, token: str)` (empty url = use discovery; saves, then `Connection.retry_now()`).
  - Status texts: CONNECTING "Connecting to Music Assistant…", RECONNECTING "Reconnecting…", AUTH_FAILED "Login failed — check token in Settings", NO_SERVER "No Music Assistant server found", connected but no local player "Waiting for this TV's speaker…".
  - Pairing: `pairingCode` set on `CODE` events from `tail_log(log_path())`; cleared when `hasLocalPlayer` becomes true or on `FAILED` (show reason in `statusText`).
- UI rules: `app.py` creates `QGuiApplication`, a `qasync.QEventLoop`, sets `QQuickStyle` to `org.kde.desktop` if available, loads `Main.qml`, starts `Connection.run()` and the log tail as tasks, calls `request_autostart()` once (remember in settings via a `autostart_requested: bool` field — add it to `AppSettings` with default `False`). `Main.qml` is a `Kirigami.ApplicationWindow` shown fullscreen; `SetupPage` is pushed when `!hasToken` or `connState == "auth_failed"`. Buttons ≥ 96px, text ≥ 28px, focus ring 4px `#4fc3f7` offset 4px, initial focus on play/pause. Back (`Qt.Key_Back`, `Qt.Key_Escape`) pops pages; on Home it opens an "Exit Couchside?" dialog (focus on "Cancel"). Media keys `Qt.Key_MediaPlay`, `Key_MediaPause`, `Key_MediaTogglePlayPause`, `Key_MediaNext`, `Key_MediaPrevious` handled via a window-level `Shortcut` so focus position doesn't matter. Text fields use the standard `TextField` (Bigscreen's virtual keyboard attaches to it).

- [ ] **Step 1: Write `tests/test_controller_text.py`** for the pure mapping `status_text(state: ConnState, has_local_player: bool) -> str` (put it in `controller.py` but import-safe without Qt, or in `core/playback.py`): the five strings above.
- [ ] **Step 2: Run** → fail. **Step 3: Implement** mapping, controller, QML. **Step 4: Run** unit tests → pass.
- [ ] **Step 5: Commit** `feat: Kirigami TV UI with connection status, transport and pairing PIN`.

### Task 8: Flatpak packaging, install and dev scripts

**Files:**
- Create: `flatpak/io.github.shreyasajj.Couchside.yml`, `.desktop`, `.metainfo.xml`, `.svg`, `flatpak/python-deps.json`, `scripts/install.sh`, `scripts/dev-deploy.sh`

**Interfaces / pinned values:**
- Manifest: `runtime: org.kde.Platform`, `runtime-version: '6.11'`, `sdk: org.kde.Sdk`, `base: io.qt.PySide.BaseApp`, `base-version: '6.11'`, `command: couchside`. `finish-args`: `--share=network`, `--share=ipc`, `--socket=wayland`, `--socket=fallback-x11`, `--device=dri`, `--socket=pulseaudio`, `--filesystem=xdg-run/pipewire-0:ro` (for the Phase 8 visualizer; drop if Flathub objects). Sendspin's MPRIS: `--own-name=org.mpris.MediaPlayer2.Sendspin.*` (check the exact bus name sendspin uses and record it).
- Modules: `portaudio` (from source tarball, for `sounddevice`), `python-deps` (generated with `flatpak-pip-generator` for `music-assistant-client`, `zeroconf`, `qasync`, `sendspin==9.1.0` and their deps; prefer sdists/manylinux wheels that build offline), then `couchside` (type `dir`, `path: ..`, `pip install --no-deps --prefix=/app .`).
- `.desktop`: `Name=Couchside`, `Comment=Music Assistant for your TV`, `Exec=couchside`, `Icon=io.github.shreyasajj.Couchside`, `Categories=AudioVideo;Audio;Player;`.
- `scripts/install.sh` (on the TV box, no sudo): installs `org.flatpak.Builder`, `org.kde.Sdk//6.11`, `io.qt.PySide.BaseApp//6.11` from `flathub --user` if missing, builds with `flatpak run org.flatpak.Builder --user --install --force-clean build-dir flatpak/io.github.shreyasajj.Couchside.yml`, then prints how to launch. Idempotent.
- `scripts/dev-deploy.sh`: rsync the repo (excluding `.venv`, `.git`, build dirs) to `mediac@192.168.30.153:~/couchside`, run the incremental build there (`--keep-build-dirs` reuse; only the `couchside` module rebuilds), and optionally launch on the TV with `flatpak run io.github.shreyasajj.Couchside` in the user's graphical session (`systemd-run --user` or the session env from `/proc/<plasmashell pid>/environ`).

- [ ] **Step 1: Generate `python-deps.json`** (`flatpak-pip-generator` on the TV box inside `org.kde.Sdk`), commit it.
- [ ] **Step 2: Run `scripts/install.sh` on the TV box** → `flatpak list --user | grep Couchside` shows the app.
- [ ] **Step 3: Sendspin check**: `flatpak run --command=couchside-sendspin io.github.shreyasajj.Couchside &` → `~/.var/app/io.github.shreyasajj.Couchside/.local/state/couchside/sendspin.log` contains `Starting Sendspin daemon:`, and the MA web UI shows a player named "Living Room TV".
- [ ] **Step 4: Commit** `build: flatpak manifest and install scripts`.

### Task 9: End-to-end on the TV and README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Launch on the TV.** Verify on the real screen:
  - The Couchside tile is on the Bigscreen home screen and opens the app.
  - First run: setup page; enter the token → "Connecting…" → home page.
  - The status reaches connected and the local player is selected (title/artist show once something plays).
  - Play/pause, next, previous work from the remote, both via focused buttons and media keys.
  - Background autostart was requested; after a reboot (ask the owner first) "Living Room TV" is in MA before the app is opened.
  - Back on the home page asks before exiting.
- [ ] **Step 2: Disconnect test**: stop the MA add-on briefly only if the owner agrees; otherwise block the route with a wrong server URL in setup → "Reconnecting…", no crash, recovers when restored.
- [ ] **Step 3: Write `README.md`**: what it is; install (`scripts/install.sh`); configure (token from MA web UI, optional manual URL); run; update (`git pull && scripts/install.sh` for now; Phase 7 adds in-app update); dev loop (`scripts/dev-deploy.sh`, Mac unit tests); **API notes**, filled with what Tasks 4–8 found: MA token required on schema 65; which player field carries the Sendspin client id; Sendspin client id = public key from `identity-daemon.json` (changed in pairing-capable releases); daemon only logs the pairing code and never logs "paired"; `sendspin daemon` arg order.
- [ ] **Step 4: Commit** `docs: README with install, configure and API notes`.
- [ ] **Step 5: Phase summary to the owner**, then stop for feedback before Phase 2.
