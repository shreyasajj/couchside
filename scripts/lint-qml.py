#!/usr/bin/env python3
"""Lint the QML with qmllint (it ships with PySide6). Every warning fails, except:

- uses of `app`: the controller is handed to QML from Python (a context property), which
  qmllint can't see. A misspelt name (`ap.title`) still fails.
- Theme.qml's "not declared as singleton in qmldir": qmllint says that only when it lints
  Theme.qml on its own; the qmldir does declare it.

Main.qml is skipped: it's a thin Kirigami window around Shell.qml, and Kirigami isn't part
of the PySide6 wheel. The whole UI lives in Shell.qml and below, which is linted.

Run: python scripts/lint-qml.py   (exit status 1 when something is wrong)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

QML = Path(__file__).resolve().parents[1] / "src/couchside/ui/qml"
SKIP = {"Main.qml"}


def qmllint() -> list[str]:
    exe = Path(sys.executable).with_name("pyside6-qmllint")
    return [str(exe)] if exe.exists() else ["pyside6-qmllint"]


def allowed(name: str, warning: dict, source: list[str]) -> bool:
    line, col, length = warning.get("line"), warning.get("column"), warning.get("length", 0)
    token = source[line - 1][col - 1:col - 1 + length] if line and col else ""
    if warning.get("id") == "unqualified" and token == "app":
        return True
    return name == "Theme.qml" and warning.get("id") == "import" and "singleton" in warning["message"]


def main() -> int:
    files = sorted(p for p in QML.glob("*.qml") if p.name not in SKIP)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "lint.json"
        subprocess.run([*qmllint(), "--json", str(out), "-I", str(QML), *map(str, files)],
                       cwd=QML, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if not out.exists():
            print("qmllint produced no report — is PySide6 installed?", file=sys.stderr)
            return 1
        report = json.loads(out.read_text())
    problems = []
    for entry in report["files"]:
        path = Path(entry["filename"])
        source = path.read_text().split("\n") if path.exists() else []
        for w in entry["warnings"]:
            if not allowed(path.name, w, source):
                where = f"{path.name}:{w.get('line', '?')}:{w.get('column', '?')}"
                problems.append(f"{where}: {w['message'].splitlines()[0]} [{w.get('id')}]")
    for p in problems:
        print(p)
    print(f"qmllint: {len(files)} files, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
