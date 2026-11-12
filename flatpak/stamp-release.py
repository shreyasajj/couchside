#!/usr/bin/env python3
"""Stamp a release build: write src/couchside/build_info.json (shown in Settings) and set
the AppStream release entry. Usage: stamp-release.py VERSION COMMIT DATE"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METAINFO = ROOT / "flatpak/io.github.shreyasajj.Couchside.metainfo.xml"
BUILD_INFO = ROOT / "src/couchside/build_info.json"


def stamp(version: str, commit: str, date: str, root: Path = ROOT) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise SystemExit(f"bad version or date: {version} {date}")
    (root / BUILD_INFO.relative_to(ROOT)).write_text(json.dumps({"version": version, "commit": commit[:12]}) + "\n")
    meta = root / METAINFO.relative_to(ROOT)
    text = meta.read_text()
    text, n = re.subn(r'<release version="[^"]*" date="[^"]*"', f'<release version="{version}" date="{date}"', text, count=1)
    if n != 1:
        raise SystemExit("no <release> entry in the metainfo")
    meta.write_text(text)


if __name__ == "__main__":
    stamp(*sys.argv[1:4])
