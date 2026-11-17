"""The numbers behind the visualizer's pictures."""

from pathlib import Path

import pytest

QtQml = pytest.importorskip("PySide6.QtQml")

JS = Path(__file__).parents[1] / "src/couchside/ui/qml/viz.js"

HELPERS = """
function ringCounts(beats) {
    var rings = [], prev = 0, seen = []
    for (var i = 0; i < beats.length; i++) {
        rings = stepRings(rings, beats[i], prev, 0.033)
        prev = beats[i]
        seen.push(rings.length)
    }
    return seen
}
function ringsAfter(seconds) {
    var rings = stepRings([], 1, 0, 0.033)
    for (var t = 0; t < seconds; t += 0.033) rings = stepRings(rings, 1, 1, 0.033)
    return rings
}
function manyBeats(n) {
    var rings = []
    for (var i = 0; i < n; i++) { rings = stepRings(rings, 1, 0, 0.001) }
    return rings.length
}
"""


@pytest.fixture
def js(qt_app):
    engine = QtQml.QJSEngine()
    result = engine.evaluate(JS.read_text().replace(".pragma library", "") + HELPERS)
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
    assert js("frame(0, 0, 1, [0.5, 0.25]).bars") == [0.5, 0.25]


def test_a_ring_starts_when_the_beat_rises_not_while_it_stays_high(js):
    assert js("ringCounts([0.1, 0.9, 0.9, 0.8, 0.2, 0.9])") == [0, 1, 1, 1, 1, 2]


def test_rings_grow_fade_and_go(js):
    ring = js("ringsAfter(0.3)")[0]
    assert ring["r"] > 130 + 0.3 * 800 and 0 < ring["a"] < 0.6
    assert js("ringsAfter(0.8)") == []                   # faded out after two thirds of a second
    assert js("manyBeats(20)") == 6                      # never more than the items that draw them


def test_spokes_and_orb_follow_the_music(js):
    assert js("spokeLength(0, 0, true)") == 200
    assert js("spokeLength(1, 1, true)") == 490 and js("spokeLength(1, 1, false)") == 370


def test_flow_lines_span_the_width_and_swell_with_the_level(js):
    quiet = js("flowPoints(2, 1.0, 0, 0, 1920, 1080, 32)")
    loud = js("flowPoints(2, 1.0, 1.4, 1, 1920, 1080, 32)")
    assert len(quiet) == 61 and quiet[0]["x"] == 0 and quiet[-1]["x"] == 1920

    def swing(points):
        ys = [p["y"] for p in points]
        return max(ys) - min(ys)
    assert swing(loud) > 3 * swing(quiet) > 0
    assert all(0 <= p["y"] <= 1080 for p in loud)        # even at full blast it stays on screen


def test_bars_never_vanish_and_jump_with_the_beat(js):
    assert js("barHeight(0, 0)") == pytest.approx(0.012)
    assert js("barHeight(1, 0)") == 0.75 and js("barHeight(1, 1)") == 1.0


def test_mix_blends_two_colours(js):
    c = js("mix({r:0,g:0,b:0}, {r:1,g:0.5,b:0}, 0.5)")
    assert (c["r"], c["g"], c["b"]) == (0.5, 0.25, 0)
    assert js("mix({r:0,g:0,b:0}, {r:1,g:1,b:1}, 7).r") == 1


def test_edge_bars_use_the_lower_four_fifths_of_the_spectrum(js):
    assert js("edgeBin(0, 48)") == 0 and js("edgeBin(47, 48)") == 50
    assert js("edgeBin(23, 24)") == 49 and js("edgeBin(999, 24)") == 63


def test_the_chase_laps_the_screen_once_every_eight_beats(js):
    assert js("chaseStep(0, 1, 120)") == pytest.approx(0.25)      # 2 beats in a second
    assert js("chaseStep(0, 1, 60)") == pytest.approx(0.125)      # half the tempo, half the speed
    assert js("chaseStep(0.9, 1, 120)") == pytest.approx(0.15)    # wraps round
    assert js("chaseStep(0.5, 0, 200)") == pytest.approx(0.5)


def test_wave_rises_and_falls_once_round_the_frame(js):
    assert js("wave(0)") == 0 and js("wave(0.5)") == 1 and js("wave(1)") == 0
    assert js("wave(0.25)") == pytest.approx(0.5) and js("wave(1.25)") == pytest.approx(0.5)


def test_perimeter_goes_round_bottom_right_top_left(js):
    assert js("perimeter('bottom', 0)") == 0
    assert js("perimeter('right', 0)") == pytest.approx(0.32)
    assert js("perimeter('top', 0)") == pytest.approx(0.5)
    assert js("perimeter('left', 0)") == pytest.approx(0.82)
    assert js("perimeter('left', 1)") == pytest.approx(1.0)


def test_glow_follows_how_loud_that_part_of_the_music_is(js):
    assert js("glow(0)") == pytest.approx(0.1)                    # quiet: a faint light, never off
    assert js("glow(0.4)") == pytest.approx(0.55)
    assert js("glow(0.8)") == pytest.approx(1.0) and js("glow(1.5)") == pytest.approx(1.0)
    assert js("glow(0.2)") < js("glow(0.3)") < js("glow(0.6)")
