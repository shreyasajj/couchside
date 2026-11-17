"""Where the remote can go: which tabs show, and where Back leads."""

from pathlib import Path

import pytest

QtQml = pytest.importorskip("PySide6.QtQml")

JS = Path(__file__).parents[1] / "src/couchside/ui/qml/nav.js"


@pytest.fixture
def nav(qt_app):
    engine = QtQml.QJSEngine()
    engine.evaluate(JS.read_text().replace(".pragma library", ""))

    def call(name, *args):
        result = engine.globalObject().property(name).call([engine.toScriptValue(a) for a in args])
        assert not result.isError(), result.toString()
        return result.toVariant()
    return call


def test_three_tabs(nav):
    assert nav("tabs") == ["now", "search", "queue"]
    assert nav("isTab", "visualizer") is False and nav("isTab", "queue") is True


def test_a_name_that_is_not_a_screen_becomes_now_playing(nav):
    assert nav("validScreen", "lyrics") == "now"          # a tab once: a button on Now Playing now
    assert nav("validScreen", "visualizer") == "visualizer"
    assert nav("validScreen", "settings") == "settings"
    assert nav("validScreen", "nope") == "now"


def test_back(nav):
    assert nav("back", "visualizer", "now") == "now"      # opened from Now Playing
    assert nav("back", "guests", "queue") == "queue"      # back to where it was opened from
    assert nav("back", "settings", "settings") == "now"   # never back to itself
    assert nav("back", "search", "search") == "now"
    assert nav("back", "now", "now") == "exit"


def test_labels(nav):
    assert nav("label", "now") == "Now Playing" and nav("label", "nope") == ""
