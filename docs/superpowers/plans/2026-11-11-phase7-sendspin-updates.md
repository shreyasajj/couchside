# Phase 7: Sendspin Updates and Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** New Couchside builds (each carrying the current Sendspin) are published as a signed Flatpak repo; the TV checks for updates on launch and daily, shows the bundled and latest Sendspin versions, and installs an update with one button, restarting Sendspin and the app. Settings gets a Sendspin section (player name, audio output, sync delay).

**Architecture:** A release workflow builds the Flatpak on every merge to main, signs it with a GPG key from a repo secret and publishes a one-commit OSTree repo plus `.flatpakrepo`/`.flatpakref` to GitHub Pages. The TV installs from that remote once; afterwards Flatpak's portal (`org.freedesktop.portal.Flatpak`: `CreateUpdateMonitor`, `UpdateMonitor.Update`, `Spawn` with the latest-version flag) updates and relaunches it from inside the sandbox. `core/updates.py` (Qt-free) does versions (bundled Sendspin via importlib.metadata, latest from PyPI JSON, build info written by CI). `core/flatpak_portal.py` talks D-Bus with jeepney (asyncio). The Sendspin supervisor rebuilds its command from settings every 2 s and restarts the daemon when it changes; a control file asks it to exit before an update relaunch.

**Spec:** [design](../specs/2026-11-10-couchside-design.md) "Packaging" (updates via the Flatpak portal; Sendspin settings screen), [AGENTS.md](../../../AGENTS.md) "Sendspin client setup" (check on launch and daily, versions in Settings, one-button upgrade + restart, settings preserved). Owner's decision (2026-11-11): publish a signed Flatpak repo on GitHub Pages.

**Branch:** `phase7-sendspin-update` from `main`.

## Decisions (spec + my calls)

- Release on every push to main that touches `src/`, `flatpak/` or `pyproject.toml` (and on demand). Version `0.7.<run number>` written into build info and the AppStream release. Pages holds only the newest commit (no history, no static deltas: about 300 MB, inside Pages' 1 GB); OSTree still downloads only changed files. x86_64 only (the TV); arm64 later if a Pi needs it.
- The signing key is made once (on the TV, which has gpg), kept as the secret `FLATPAK_GPG_PRIVATE_KEY`, with a backup at `~/.config/couchside-release/` on the Mac (0600). The public key goes into the `.flatpakrepo`/`.flatpakref`.
- `python-deps.json` is generated at build time (CI, release, install.sh), no longer committed, so a Dependabot bump of `flatpak/requirements.txt` builds the new Sendspin without a manual step. Dependabot watches `/flatpak` too; its PRs auto-merge as before, and the merge publishes a release.
- In the app: "Sendspin 9.1.0 · latest 9.1.0" (PyPI, checked on launch and every 24 h, failures shown as "couldn't check"); "Couchside 0.7.N"; an update row that says Up to date / Update available / Updating… N% / Restarting…, and outside a published install (dev builds) "Updates come from the published Couchside repo". OK on "Update available": the portal updates, the Sendspin supervisor is asked to exit, the new Sendspin supervisor and the new app are spawned at the latest version, the old app quits.
- Sendspin section: Player name (text, default "Living Room TV"), Audio output (cycles "Default" and the devices `sendspin audio-devices list` reports, stored by name), Sync delay (cycles 0, 25, 50, 100, 150, 200, 300, 500 ms). Changes save and the supervisor restarts the daemon within ~2 s. Sendspin's own files in its settings dir are never touched.

## Global Constraints

- No sandbox escapes: only the Flatpak portal (no `flatpak-spawn --host`, no `org.freedesktop.Flatpak` talk-name).
- Never crash on a missing portal, no network, or a failed update; show it in the row.
- TV UX rules (D-pad, focus never lost, ≥ 28 px, plain-text labels).
- Commit messages never mention Claude Code; they end with the Co-Authored-By line.

## Review Focus

- Update flow when the portal is missing, the app isn't from a remote, or the update fails midway: the app keeps running and says why.
- Supervisor restart on a settings change must not leave two daemons or a stale port.
- A device name with odd characters (spaces, parentheses, colons) passes through to `--audio-device` intact.
- Release workflow must never publish an unsigned repo or a repo with the Debug extension.
- PyPI unreachable or returning junk: the version row says it couldn't check.

## Tasks

1. **Sendspin settings + live supervisor** — settings `sendspin_audio_device`, `sendspin_delay_ms`; `build_daemon_argv` adds `--audio-device` / `--output-delay-ms`; `supervise(argv_factory, …)` restarts when the argv changes and exits on a control request; `parse_audio_devices(text)`.
2. **Versions** — `core/updates.py`: `bundled_sendspin_version()`, `latest_sendspin_version(http)`, `is_newer(a, b)`, `build_info()`.
3. **Portal** — `core/flatpak_portal.py` (jeepney): `in_flatpak()`, `UpdateMonitor` (available / progress callbacks, `update()`), `spawn_latest(argv)`.
4. **TV** — controller properties/slots for versions, update state, Sendspin settings; daily check; Settings "Sendspin" and "Updates" sections.
5. **Release** — `release.yml`, generated `python-deps.json`, Dependabot `/flatpak`, install.sh; signing key + Pages; first release; TV moved to the published remote; second release to test the in-app update end to end.
6. **Docs + PR.**
