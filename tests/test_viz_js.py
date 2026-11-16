"""The visualizer's drawing code, run against a pretend canvas."""

from pathlib import Path

import pytest

QtQml = pytest.importorskip("PySide6.QtQml")

JS = Path(__file__).parents[1] / "src/couchside/ui/qml/viz.js"

# a canvas context that only counts what is asked of it
FAKE_CTX = """
function fakeCtx() {
    var calls = {}
    function count(name) { return function() { calls[name] = (calls[name] || 0) + 1; return gradient } }
    var gradient = { addColorStop: function() {} }
    var ctx = { calls: calls }
    var names = ["fillRect", "beginPath", "moveTo", "lineTo", "arc", "arcTo", "closePath", "stroke",
                 "fill", "save", "restore", "translate", "rotate", "createRadialGradient",
                 "createLinearGradient"]
    for (var i = 0; i < names.length; i++) ctx[names[i]] = count(names[i])
    return ctx
}
function run(mode, energy, beat, bars, frames) {
    var st = newState(), ctx = fakeCtx()
    for (var i = 0; i < (frames || 1); i++) draw(mode, ctx, 1920, 1080, frame(energy, beat, 1, bars), st)
    return { painted: (ctx.calls.fill || 0) + (ctx.calls.stroke || 0), rings: st.rings.length }
}
function ringsOver(beats) {
    var st = newState(), ctx = fakeCtx(), seen = []
    for (var i = 0; i < beats.length; i++) {
        radial(ctx, 1920, 1080, frame(0.5, beats[i], 1, null), st)
        seen.push(st.rings.length)
    }
    return seen
}
"""


@pytest.fixture
def js(qt_app):
    engine = QtQml.QJSEngine()
    result = engine.evaluate(JS.read_text().replace(".pragma library", "") + FAKE_CTX)
    assert not result.isError(), result.toString()

    def call(expr):
        value = engine.evaluate(expr)
        assert not value.isError(), value.toString()
        return value.toVariant()
    return call


def test_a_frame_scales_the_beat_by_the_intensity(js):
    f = js("frame(0.5, 1, 2, null)")
    assert f["beat"] == 2 and f["level"] == 1.4          # min(1.4, 2 * 0.8)
    assert f["kick"] == 1 and len(f["bars"]) == 64 and not any(f["bars"])
    assert js("frame(0.5, 0.5, 1, null).level") == pytest.approx(0.4)
    assert js("frame(0.2, 1, 0, null).beat") == 0        # intensity 0: no hit at all


@pytest.mark.parametrize("mode", ["radial", "flow", "bars"])
def test_every_mode_draws_with_music_and_in_silence(js, mode):
    loud = js(f"run('{mode}', 0.8, 1, (function(){{var b=[];for(var i=0;i<64;i++)b.push(i/64);return b}})(), 3)")
    quiet = js(f"run('{mode}', 0, 0, null, 3)")
    assert loud["painted"] > 0 and quiet["painted"] > 0


def test_an_unknown_mode_draws_the_first_one(js):
    assert js("run('nope', 0.5, 0, null).painted") > 0


def test_a_ring_starts_when_the_beat_rises_not_while_it_stays_high(js):
    seen = js("ringsOver([0.1, 0.9, 0.9, 0.8, 0.2, 0.9])")
    assert seen == [0, 1, 1, 1, 1, 2]
