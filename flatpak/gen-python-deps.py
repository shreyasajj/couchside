#!/usr/bin/env python3
"""Generate flatpak/python-deps.json: pinned PyPI files (url + sha256) for an offline build.

Run inside the target SDK so pip picks wheels for the runtime's Python/platform:

    flatpak run --share=network --filesystem="$PWD" --command=python3 \
        org.kde.Sdk//6.11 flatpak/gen-python-deps.py

PySide6 is excluded: it comes from io.qt.PySide.BaseApp.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIREMENTS = HERE / "requirements.txt"
OUTPUT = HERE / "python-deps.json"
EXCLUDE = {"pyside6", "pyside6-essentials", "pyside6-addons", "shiboken6"}


def _get_json(url: str):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def fetch_json(url: str, get=_get_json, sleep=time.sleep, attempts: int = 5):
    """PyPI's JSON API, retried with backoff: CI runners see the odd dropped connection
    (e.g. SSL UNEXPECTED_EOF) and one blip shouldn't fail a 40-package release."""
    for attempt in range(attempts):
        try:
            return get(url)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == attempts - 1:
                raise
            print(f"  retrying {url}: {e}", file=sys.stderr)
            sleep(2 ** (attempt + 1))


def pypi_url(filename: str, name: str, version: str) -> str:
    data = fetch_json(f"https://pypi.org/pypi/{name}/{version}/json")
    for f in data["urls"]:
        if f["filename"] == filename:
            return f["url"]
    raise SystemExit(f"{filename} not found on PyPI")


def name_version(filename: str) -> tuple[str, str]:
    stem = filename
    for ext in (".whl", ".tar.gz", ".zip"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
    if filename.endswith(".whl"):
        name, version = stem.split("-")[:2]
    else:
        name, _, version = stem.rpartition("-")
    return name, version


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [sys.executable, "-m", "pip", "download", "--retries", "5", "--timeout", "30",
             "--dest", tmp, "-r", str(REQUIREMENTS)],
            check=True,
        )
        sources = []
        for path in sorted(Path(tmp).iterdir()):
            name, version = name_version(path.name)
            if name.lower().replace("_", "-") in EXCLUDE:
                continue
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            sources.append({"type": "file", "url": pypi_url(path.name, name, version), "sha256": sha})
            print(f"  {path.name}")

    reqs = " ".join(
        line.split("#")[0].strip()
        for line in REQUIREMENTS.read_text().splitlines()
        if line.split("#")[0].strip()
    )
    module = {
        "name": "python-deps",
        "buildsystem": "simple",
        "build-commands": [
            "pip3 install --verbose --exists-action=i --no-index --find-links=\"file://${PWD}\" "
            f"--prefix=${{FLATPAK_DEST}} --no-build-isolation {reqs}"
        ],
        "sources": sources,
    }
    OUTPUT.write_text(json.dumps(module, indent=2) + "\n")
    print(f"wrote {OUTPUT} ({len(sources)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
