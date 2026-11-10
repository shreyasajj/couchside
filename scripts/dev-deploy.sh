#!/usr/bin/env bash
# Dev loop: copy this checkout to the TV box, rebuild the Flatpak there, optionally launch it.
#   scripts/dev-deploy.sh            # sync + build + install
#   scripts/dev-deploy.sh --run      # … and (re)start the app on the TV screen
set -euo pipefail

TV="${COUCHSIDE_TV:-mediac@192.168.30.153}"
APP_ID=io.github.shreyasajj.Couchside
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

rsync -az --delete \
  --exclude .git --exclude .venv --exclude .superpowers --exclude '__pycache__' \
  --exclude '*.egg-info' --exclude build-dir --exclude .flatpak-builder \
  "$ROOT/" "$TV:couchside/"

ssh "$TV" 'bash ~/couchside/scripts/install.sh' 2>&1 | tail -n 25

if [[ "${1:-}" == "--run" ]]; then
  # Launch inside the logged-in graphical session (environment taken from plasmashell).
  ssh "$TV" "bash -s" <<REMOTE
set -e
pkill -f 'couchside.ui.app|bin/couchside\$' || true
PID=\$(pgrep -u "\$USER" -x plasmashell | head -1)
[ -n "\$PID" ] || { echo "no plasmashell running"; exit 1; }
while IFS= read -r -d '' kv; do
  case "\$kv" in WAYLAND_DISPLAY=*|DISPLAY=*|XDG_RUNTIME_DIR=*|DBUS_SESSION_BUS_ADDRESS=*|XDG_SESSION_TYPE=*|XDG_CURRENT_DESKTOP=*|QT_*) export "\$kv";; esac
done < /proc/\$PID/environ
nohup flatpak run $APP_ID > ~/couchside-run.log 2>&1 &
sleep 6
tail -n 40 ~/couchside-run.log
REMOTE
fi
