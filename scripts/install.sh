#!/usr/bin/env bash
# Build and install Couchside as a user Flatpak on this machine. No sudo needed.
# Idempotent: re-run after `git pull` to update.
set -euo pipefail

APP_ID=io.github.shreyasajj.Couchside
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$ROOT/flatpak/$APP_ID.yml"
BUILD_DIR="${COUCHSIDE_BUILD_DIR:-$HOME/.cache/couchside-build}"

need() {
  if ! flatpak info --user "$1" >/dev/null 2>&1 && ! flatpak info --system "$1" >/dev/null 2>&1; then
    echo "Installing $1 …"
    flatpak install --user -y --noninteractive flathub "$1"
  fi
}

command -v flatpak >/dev/null || { echo "flatpak is not installed" >&2; exit 1; }
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
need org.flatpak.Builder
need org.kde.Platform//6.11
need org.kde.Sdk//6.11
need io.qt.PySide.BaseApp//6.11

mkdir -p "$BUILD_DIR"
cd "$ROOT"
echo "Resolving Python dependencies …"
flatpak run --share=network --filesystem="$ROOT" --command=python3 org.kde.Sdk//6.11 \
  flatpak/gen-python-deps.py >/dev/null
flatpak run --filesystem="$ROOT" --filesystem="$BUILD_DIR" org.flatpak.Builder \
  --user --install --force-clean --ccache \
  --state-dir="$BUILD_DIR/state" "$BUILD_DIR/build" "$MANIFEST"

echo
echo "Installed. Start it from the Couchside tile on the Bigscreen home screen,"
echo "or run: flatpak run $APP_ID"
