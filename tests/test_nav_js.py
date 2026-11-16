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


def test_tabs_follow_the_settings(nav):
    assert nav("tabs", True, True) == ["now", "search", "queue", "lyrics", "visualizer"]
    assert nav("tabs", False, True) == ["now", "search", "queue", "visualizer"]
    assert nav("tabs", False, False) == ["now", "search", "queue"]


def test_a_screen_whose_tab_was_switched_off_becomes_now_playing(nav):
    assert nav("validScreen", "lyrics", False, True) == "now"
    assert nav("validScreen", "visualizer", True, False) == "now"
    assert nav("validScreen", "lyrics", True, True) == "lyrics"
    assert nav("validScreen", "settings", False, False) == "settings"   # not a tab: stays


def test_back(nav):
    assert nav("back", "guests", "queue") == "queue"      # back to where it was opened from
    assert nav("back", "settings", "settings") == "now"   # never back to itself
    assert nav("back", "search", "search") == "now"
    assert nav("back", "now", "now") == "exit"


def test_labels(nav):
    assert nav("label", "now") == "Now Playing" and nav("label", "nope") == ""
