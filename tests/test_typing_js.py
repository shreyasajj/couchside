"""The helper that decides whether a key press is typing (letters from a keyboard remote)."""

from pathlib import Path

import pytest

QtQml = pytest.importorskip("PySide6.QtQml")

JS = Path(__file__).parents[1] / "src/couchside/ui/qml/typing.js"
SHIFT, CTRL, ALT, META = 0x02000000, 0x04000000, 0x08000000, 0x10000000


@pytest.fixture
def typed(qt_app):
    engine = QtQml.QJSEngine()
    src = JS.read_text().replace(".pragma library", "")
    engine.evaluate(src)
    fn = engine.globalObject().property("typed")

    def call(text, modifiers=0):
        ev = engine.newObject()
        ev.setProperty("text", text)
        ev.setProperty("modifiers", modifiers)
        return fn.call([ev]).toString()
    return call


def test_letters_digits_and_symbols_are_typing(typed):
    assert typed("a") == "a" and typed("Z", SHIFT) == "Z" and typed("7") == "7" and typed("é") == "é"
    assert typed("-") == "-"


def test_controls_and_shortcuts_are_not(typed):
    assert typed("") == ""          # arrows, OK, Back, media keys
    assert typed(" ") == ""         # space presses the focused button
    assert typed("\r") == "" and typed("\t") == "" and typed("\x1b") == "" and typed("\x7f") == ""
    assert typed("a", CTRL) == "" and typed("a", ALT) == "" and typed("a", META) == ""


def test_js_helpers_are_packaged():
    text = (Path(__file__).parents[1] / "pyproject.toml").read_text()
    assert '"qml/*.js"' in text
