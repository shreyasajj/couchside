.pragma library

// The numbers behind the visualizer's pictures. The pictures themselves are ordinary
// Qt Quick items (VisualizerPage.qml) so the graphics card draws them; a software canvas
// redrawn 30 times a second cost most of a CPU core. Everything is in the picture's own
// units: 1920 x 1080, scaled to the screen.

var BARS = 64
var RING_START = 130      // a ring's radius when it is born (the orb's resting size)
var MAX_RINGS = 6

function zeros() {
    var z = new Array(BARS)
    for (var i = 0; i < BARS; i++) z[i] = 0
    return z
}

// One frame of what the music is doing: `energy` and `beat` are 0..1 from the beat
// detector; `intensity` (0..2.4) is how hard the picture hits on a beat; `bars` is the
// spectrum (64 values) or nothing.
function frame(energy, beat, intensity, bars) {
    var hit = beat * intensity
    return { energy: energy, kick: beat, beat: hit,
             level: Math.min(1.4, hit * (0.5 + energy * 0.6)),
             bars: bars && bars.length ? bars : zeros() }
}

// A colour between two (each { r, g, b } with 0..1 parts), t = 0..1.
function mix(a, b, t) {
    t = Math.max(0, Math.min(1, t))
    return { r: a.r + (b.r - a.r) * t, g: a.g + (b.g - a.g) * t, b: a.b + (b.b - a.b) * t }
}

// Radial Pulse: the rings moving outward. Returns the rings after `dt` seconds: each
// grows and fades, and a new one starts when the beat rises past the middle (not while
// it stays high). A ring is { r, a }: radius and strength (1 → 0).
function stepRings(rings, beat, prevBeat, dt) {
    var out = []
    for (var i = 0; i < rings.length; i++) {
        var a = rings[i].a - dt * 1.5
        if (a > 0) out.push({ r: rings[i].r + dt * 820, a: a })
    }
    if (beat > 0.55 && prevBeat <= 0.55) out.push({ r: RING_START, a: 1 })
    if (out.length > MAX_RINGS) out = out.slice(out.length - MAX_RINGS)
    return out
}

// Radial Pulse: how long the spokes are (odd ones jump with the beat) and how big the orb.
function spokeLength(energy, beat, odd) { return 200 + energy * 170 + (odd ? beat * 120 : 0) }
function orbRadius(level) { return 130 + level * 120 }

// Flow Lines: ribbon `line` (0..4) at time `t`, as points across the width every `step`.
function flowPoints(line, t, level, energy, W, H, step) {
    var phase = t * 1.2 + line * 1.4
    var amp = 70 + level * 270 * (1 - line * 0.12) + energy * 40
    var yBase = H / 2 + (line - 2) * 72
    var pts = []
    for (var x = 0; x <= W; x += step) {
        var k = x / W
        pts.push({ x: x, y: yBase + Math.sin(k * 6.5 + phase) * amp * Math.sin(k * Math.PI)
                              + Math.sin(k * 15 + phase * 1.7) * amp * 0.22 })
    }
    return pts
}

// Bars: one bar's height as a share of the tallest (never quite nothing, so the row shows).
function barHeight(value, beat) { return Math.max(0.012, value * (0.75 + 0.25 * Math.min(1.5, beat))) }

// Edge Lights: which of the 64 spectrum bars drives bar `i` of `n` along an edge (the top
// fifth of the spectrum is nearly always empty, so the edge uses the rest).
function edgeBin(i, n) { return Math.min(BARS - 1, Math.floor(i * (BARS * 0.8) / n)) }
