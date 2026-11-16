.pragma library

// The visualizer's three drawings, for a 2D canvas context. Each takes the context, the
// drawing size, one frame of what the music is doing (see frame()) and a state object
// that lives across frames: { t, dt, spin, rings, prevBeat, c1, c2 } with the two accent
// colours as { r, g, b } (0..255). They only read `a` and write `st`.

var BARS = 64

function zeros() {
    var z = new Array(BARS)
    for (var i = 0; i < BARS; i++) z[i] = 0
    return z
}

// One frame: `energy` and `beat` are 0..1 from the beat detector; `intensity` (0..2.4) is
// how hard the picture hits on a beat; `bars` is the spectrum (64 values) or nothing.
function frame(energy, beat, intensity, bars) {
    var hit = beat * intensity
    return { energy: energy, kick: beat, beat: hit,
             level: Math.min(1.4, hit * (0.5 + energy * 0.6)),
             bars: bars && bars.length ? bars : zeros() }
}

function newState() {
    return { t: 0, dt: 0.033, spin: 0, rings: [], prevBeat: 0,
             c1: { r: 0, g: 224, b: 198 }, c2: { r: 255, g: 61, b: 166 } }
}

function rgba(c, a) { return "rgba(" + c.r + "," + c.g + "," + c.b + "," + a + ")" }

function mix(st, t) {
    var a = st.c1, b = st.c2
    return { r: Math.round(a.r + (b.r - a.r) * t), g: Math.round(a.g + (b.g - a.g) * t),
             b: Math.round(a.b + (b.b - a.b) * t) }
}

function roundRect(ctx, x, y, w, h, r) {
    r = Math.max(0, Math.min(r, w / 2, h / 2))
    ctx.beginPath()
    ctx.moveTo(x + r, y)
    ctx.arcTo(x + w, y, x + w, y + h, r)
    ctx.arcTo(x + w, y + h, x, y + h, r)
    ctx.arcTo(x, y + h, x, y, r)
    ctx.arcTo(x, y, x + w, y, r)
    ctx.closePath()
}

// A glowing orb with turning spokes; every beat sends a ring outward.
function radial(ctx, W, H, a, st) {
    ctx.fillStyle = "rgba(5,5,8,0.30)"   // not a clear: the last frames linger as trails
    ctx.fillRect(0, 0, W, H)
    var cx = W / 2, cy = H / 2
    var dt = st.dt || 0.033

    st.spin += (0.12 + a.energy * 1.3) * dt
    var spokes = 56
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(st.spin)
    ctx.strokeStyle = rgba(st.c1, 0.045 + a.energy * 0.07)
    ctx.lineWidth = 2
    for (var i = 0; i < spokes; i++) {
        var ang = i / spokes * Math.PI * 2
        var len = 200 + a.energy * 170 + (i % 2 ? a.beat * 120 : 0)
        ctx.beginPath()
        ctx.moveTo(Math.cos(ang) * 120, Math.sin(ang) * 120)
        ctx.lineTo(Math.cos(ang) * (120 + len), Math.sin(ang) * (120 + len))
        ctx.stroke()
    }
    ctx.restore()

    // a ring starts each time the beat rises past the middle
    if (a.beat > 0.55 && st.prevBeat <= 0.55) st.rings.push({ r: 130, a: 1 })
    st.prevBeat = a.beat
    for (var k = st.rings.length - 1; k >= 0; k--) {
        var ring = st.rings[k]
        ring.r += dt * 820
        ring.a -= dt * 1.5
        if (ring.a <= 0) { st.rings.splice(k, 1); continue }
        ctx.strokeStyle = rgba(mix(st, Math.min(1, (ring.r - 130) / 560)), ring.a * 0.6)
        ctx.lineWidth = 6 + ring.a * 12
        ctx.beginPath()
        ctx.arc(cx, cy, ring.r, 0, Math.PI * 2)
        ctx.stroke()
    }

    var orb = 130 + a.level * 120
    var g = ctx.createRadialGradient(cx, cy, 0, cx, cy, orb * 1.7)
    g.addColorStop(0, rgba(st.c2, 0.95))
    g.addColorStop(0.4, rgba(st.c1, 0.78))
    g.addColorStop(1, "rgba(0,0,0,0)")
    ctx.fillStyle = g
    ctx.beginPath()
    ctx.arc(cx, cy, orb * 1.7, 0, Math.PI * 2)
    ctx.fill()

    ctx.fillStyle = "rgba(255,255,255,0.92)"
    ctx.beginPath()
    ctx.arc(cx, cy, orb * 0.32, 0, Math.PI * 2)
    ctx.fill()
}

// Five ribbons across the screen that swell with the music. Each is drawn twice (wide
// and faint, then narrow and bright): a glow without the cost of a blurred shadow.
function flow(ctx, W, H, a, st) {
    ctx.fillStyle = "rgba(5,5,8,0.20)"
    ctx.fillRect(0, 0, W, H)
    var lines = 5
    for (var L = 0; L < lines; L++) {
        var t = st.t * 1.2 + L * 1.4
        var amp = 70 + a.level * 270 * (1 - L * 0.12) + a.energy * 40
        var yBase = H / 2 + (L - 2) * 72
        var col = mix(st, L / (lines - 1))
        for (var pass = 0; pass < 2; pass++) {
            ctx.beginPath()
            for (var x = 0; x <= W; x += 16) {
                var k = x / W
                var y = yBase + Math.sin(k * 6.5 + t) * amp * Math.sin(k * Math.PI)
                        + Math.sin(k * 15 + t * 1.7) * amp * 0.22
                if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
            }
            ctx.strokeStyle = rgba(col, pass === 0 ? 0.16 : 0.92)
            ctx.lineWidth = pass === 0 ? 22 + a.level * 26 : 4 + a.level * 5
            ctx.stroke()
        }
    }
}

// The spectrum: 64 bars, low notes on the left, each with a faint reflection.
function bars(ctx, W, H, a, st) {
    ctx.fillStyle = "#050507"
    ctx.fillRect(0, 0, W, H)
    var values = a.bars, n = values.length
    var bw = W / n, gap = 7
    var baseY = H * 0.80
    for (var i = 0; i < n; i++) {
        var v = Math.max(0.012, values[i] * (0.75 + 0.25 * Math.min(1.5, a.beat)))
        var h = v * H * 0.6
        var x = i * bw
        var col = mix(st, i / (n - 1))
        var grad = ctx.createLinearGradient(0, baseY - h, 0, baseY)
        grad.addColorStop(0, rgba(col, 1))
        grad.addColorStop(1, rgba(st.c1, 0.18))
        ctx.fillStyle = grad
        roundRect(ctx, x + gap / 2, baseY - h, bw - gap, h, 6)
        ctx.fill()
        ctx.globalAlpha = 0.13
        ctx.fillStyle = rgba(col, 1)
        roundRect(ctx, x + gap / 2, baseY + 8, bw - gap, h * 0.32, 4)
        ctx.fill()
        ctx.globalAlpha = 1
    }
}

function draw(mode, ctx, W, H, a, st) {
    if (mode === "flow") flow(ctx, W, H, a, st)
    else if (mode === "bars") bars(ctx, W, H, a, st)
    else radial(ctx, W, H, a, st)
}
