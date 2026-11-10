# Couchside

A TV-first [Music Assistant](https://music-assistant.io) app for **KDE Plasma Bigscreen**.
It turns the TV into a Music Assistant speaker (through a bundled
[Sendspin](https://www.sendspin-audio.com) client) and a remote-friendly player.

Status: **Phase 1 (foundation)**: connect, bundled speaker, play/pause/next/previous.
Now Playing, search, lyrics, guest mode and admin access follow in later phases
(see [Agents.md](Agents.md) and the [design](docs/superpowers/specs/2026-11-10-couchside-design.md)).

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

Remote: arrows move focus, OK activates, Back goes back (on the home screen it asks
before exiting). Media keys (play/pause, next, previous) work anywhere.

## Update

```bash
cd ~/couchside && git pull && scripts/install.sh
```

Settings, the token and Sendspin's identity are kept. (Phase 7 adds an in-app update button.)

## Develop

- **Unit tests** (any machine, no Qt needed):
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
- **Flatpak instead of `uv` + systemd** (owner's decision, see design doc):
  Sendspin is bundled and autostarted through the Background portal.
