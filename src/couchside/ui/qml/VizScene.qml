import QtQuick
import QtQuick.Shapes
import "viz.js" as Viz

// The visualizer's pictures: ordinary items the graphics card draws, moved 30 times a
// second. Everything is laid out for 1920 x 1080 and scaled to the width it is given. One
// timer reads the music (level, beat, spectrum) and sets a handful of numbers; nothing is
// painted in software. Used full-screen by the Visualizer and behind the words on Now
// Playing. Edge Lights is a picture of its own and can also lie over the others.
Item {
    id: root
    property bool running: false                   // on screen, app in front
    property string mode: app.visualizerMode       // radial | flow | bars | edge
    property string colours: app.visualizerColours // accent | rainbow | beat
    property bool edges: app.visualizerEdges        // edge lights over the other pictures too
    clip: true

    Item {
        id: scene
        width: 1920
        height: 1080
        scale: root.width / width
        transformOrigin: Item.TopLeft

        readonly property string mode: root.mode
        property real energy: 0
        property real beat: 0          // 0..intensity: this frame's hit
        property real level: 0
        property var bars: Viz.zeros()
        property real t: 0
        property real spin: 0
        property var rings: []
        property var flow: []          // five ribbons, each a list of points
        property real prevBeat: 0
        property real phase: 0         // Edge Lights: how far the colours have run round (0..1)
        readonly property bool edgeShown: mode === "edge" || root.edges
        // a point on the frame (0..1 round it) -> its colour, moved on by the chase
        function chase(pos) {
            var p = pos + phase
            if (root.colours === "rainbow") return Qt.hsla(((p % 1) + 1) % 1, 1.0, 0.56, 1)
            return blend(Viz.wave(p))
        }
        property double last: 0
        // 0..1 along the picture -> a colour: between the look's two colours, round the
        // colour wheel, or a family of neighbours that steps round the wheel on every beat
        function blend(amount) {
            amount = Math.max(0, Math.min(1, amount))
            if (root.colours === "rainbow") return Qt.hsla(amount * 0.83, 1.0, 0.56, 1)
            if (root.colours === "beat") return Qt.hsla((app.beatHue + amount * 0.14) % 1, 1.0, 0.56, 1)
            var c = Viz.mix(Theme.a1, Theme.a2, amount)
            return Qt.rgba(c.r, c.g, c.b, 1)
        }
        readonly property color c1: blend(0)
        readonly property color c2: blend(1)

        function tick() {
            var now = Date.now() / 1000
            var dt = last > 0 ? Math.min(0.1, now - last) : 0.033
            last = now
            var a = Viz.frame(app.vizEnergy, app.vizBeat, app.visualizerIntensity, app.spectrum)
            energy = a.energy
            beat = a.beat
            level = a.level
            t += dt
            if (mode === "bars" || edgeShown) bars = a.bars
            if (edgeShown) phase = Viz.chaseStep(phase, dt, app.vizTempo)
            if (mode === "flow") {
                var lines = []
                for (var i = 0; i < 5; i++) {
                    var pts = Viz.flowPoints(i, t, level, energy, width, height, 32)
                    lines.push(pts.map(function(p) { return Qt.point(p.x, p.y) }))
                }
                flow = lines
            } else if (mode === "radial") {
                spin += (0.12 + energy * 1.3) * dt
                rings = Viz.stepRings(rings, beat, prevBeat, dt)
            }
            prevBeat = beat
        }

        // Radial Pulse: turning spokes and a ring sent out on every beat.
        Item {
            visible: scene.mode === "radial"
            x: scene.width / 2
            y: scene.height / 2

            Item {   // the spokes
                rotation: scene.spin * 180 / Math.PI
                opacity: 0.09 + scene.energy * 0.14
                Repeater {
                    model: 56
                    delegate: Item {
                        required property int index
                        rotation: index * 360 / 56
                        Rectangle {
                            x: -1
                            y: 120
                            width: 2
                            height: Viz.spokeLength(scene.energy, scene.beat, index % 2 === 1)
                            color: scene.c1
                            antialiasing: true
                        }
                    }
                }
            }
            Repeater {   // the rings
                model: Viz.MAX_RINGS
                delegate: Rectangle {
                    required property int index
                    readonly property var ring: index < scene.rings.length ? scene.rings[index] : null
                    visible: ring !== null
                    width: ring ? ring.r * 2 : 0
                    height: width
                    x: -width / 2
                    y: -height / 2
                    radius: width / 2
                    color: "transparent"
                    antialiasing: true
                    border.width: ring ? 6 + ring.a * 12 : 0
                    border.color: ring ? scene.blend((ring.r - Viz.RING_START) / 560) : "transparent"
                    opacity: ring ? ring.a * 0.6 : 0
                }
            }
        }

        // Flow Lines: five ribbons, each a bright line over a wide faint one (its glow).
        Repeater {
            model: scene.mode === "flow" ? 5 : 0
            delegate: Shape {
                id: ribbon
                required property int index
                readonly property color tone: scene.blend(index / 4)
                readonly property var points: index < scene.flow.length ? scene.flow[index] : []
                anchors.fill: parent
                ShapePath {
                    strokeColor: Theme.tint(ribbon.tone, 0.16)
                    strokeWidth: 22 + scene.level * 26
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    joinStyle: ShapePath.RoundJoin
                    PathPolyline { path: ribbon.points }
                }
                ShapePath {
                    strokeColor: Theme.tint(ribbon.tone, 0.92)
                    strokeWidth: 4 + scene.level * 5
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    joinStyle: ShapePath.RoundJoin
                    PathPolyline { path: ribbon.points }
                }
            }
        }

        // Bars: the spectrum, low notes on the left, each with a faint reflection.
        Repeater {
            model: scene.mode === "bars" ? Viz.BARS : 0
            delegate: Item {
                id: bar
                required property int index
                readonly property real h: Viz.barHeight(scene.bars[index] || 0, scene.beat) * scene.height * 0.6
                readonly property color tone: scene.blend(index / (Viz.BARS - 1))
                x: index * scene.width / Viz.BARS
                Rectangle {
                    x: 3.5
                    y: scene.height * 0.8 - bar.h
                    width: scene.width / Viz.BARS - 7
                    height: bar.h
                    radius: 6
                    gradient: Gradient {
                        GradientStop { position: 0; color: bar.tone }
                        GradientStop { position: 1; color: Theme.tint(scene.c1, 0.18) }
                    }
                }
                Rectangle {
                    x: 3.5
                    y: scene.height * 0.8 + 8
                    width: scene.width / Viz.BARS - 7
                    height: bar.h * 0.32
                    radius: 4
                    color: bar.tone
                    opacity: 0.13
                }
            }
        }

        // Edge Lights: the spectrum growing in from all four edges of the screen, each bar
        // solid colour at the edge and fading inward, round a thin rim of light that flashes
        // on the beat. The colours run round the frame, one lap every eight beats, so they
        // speed up and slow down with the song. The middle stays clear, so it lies over the
        // other pictures too (and lyrics on Now Playing); lights behind the TV that copy the
        // screen's edges move with it.
        Item {
            id: edge
            anchors.fill: parent
            visible: scene.edgeShown
            readonly property int across: 48     // bars along the top and the bottom
            readonly property int down: 24       // bars along each side
            readonly property real rim: 18
            readonly property real flash: Math.min(1, 0.25 + 0.5 * scene.beat + 0.3 * scene.energy)
            function value(i, n) { return Viz.barHeight(scene.bars[Viz.edgeBin(i, n)] || 0, scene.beat) }
            function at(side, along) { return scene.chase(Viz.perimeter(side, along)) }

            Repeater {   // bottom (low notes on the left) and top (mirrored)
                model: edge.visible ? edge.across * 2 : 0
                delegate: Rectangle {
                    required property int index
                    readonly property bool atTop: index >= edge.across
                    readonly property int slot: atTop ? index - edge.across : index
                    readonly property real len: edge.value(slot, edge.across) * scene.height * 0.3
                    readonly property color tone: edge.at(atTop ? "top" : "bottom", (slot + 0.5) / edge.across)
                    x: (atTop ? edge.across - 1 - slot : slot) * scene.width / edge.across + 4
                    y: atTop ? 0 : scene.height - len
                    width: scene.width / edge.across - 8
                    height: len
                    gradient: Gradient {
                        GradientStop { position: 0; color: atTop ? tone : Theme.tint(tone, 0) }
                        GradientStop { position: 1; color: atTop ? Theme.tint(tone, 0) : tone }
                    }
                }
            }
            Repeater {   // left (low notes at the bottom) and right (mirrored)
                model: edge.visible ? edge.down * 2 : 0
                delegate: Rectangle {
                    required property int index
                    readonly property bool atRight: index >= edge.down
                    readonly property int slot: atRight ? index - edge.down : index
                    readonly property real len: edge.value(slot, edge.down) * scene.width * 0.16
                    readonly property color tone: edge.at(atRight ? "right" : "left", (edge.down - 1 - slot + 0.5) / edge.down)
                    x: atRight ? scene.width - len : 0
                    y: (atRight ? slot : edge.down - 1 - slot) * scene.height / edge.down + 4
                    width: len
                    height: scene.height / edge.down - 8
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: atRight ? Theme.tint(tone, 0) : tone }
                        GradientStop { position: 1; color: atRight ? tone : Theme.tint(tone, 0) }
                    }
                }
            }

            // the rim: bottom, top, left, right (colours sampled along each side)
            Rectangle {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                height: edge.rim; opacity: edge.flash
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: edge.at("bottom", 0) }
                    GradientStop { position: 0.25; color: edge.at("bottom", 0.25) }
                    GradientStop { position: 0.5; color: edge.at("bottom", 0.5) }
                    GradientStop { position: 0.75; color: edge.at("bottom", 0.75) }
                    GradientStop { position: 1; color: edge.at("bottom", 1) }
                }
            }
            Rectangle {
                anchors { left: parent.left; right: parent.right; top: parent.top }
                height: edge.rim; opacity: edge.flash
                gradient: Gradient {   // the top runs right to left
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: edge.at("top", 1) }
                    GradientStop { position: 0.25; color: edge.at("top", 0.75) }
                    GradientStop { position: 0.5; color: edge.at("top", 0.5) }
                    GradientStop { position: 0.75; color: edge.at("top", 0.25) }
                    GradientStop { position: 1; color: edge.at("top", 0) }
                }
            }
            Rectangle {
                anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                width: edge.rim; opacity: edge.flash
                gradient: Gradient {   // the left runs top to bottom
                    GradientStop { position: 0; color: edge.at("left", 0) }
                    GradientStop { position: 0.5; color: edge.at("left", 0.5) }
                    GradientStop { position: 1; color: edge.at("left", 1) }
                }
            }
            Rectangle {
                anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
                width: edge.rim; opacity: edge.flash
                gradient: Gradient {   // the right runs bottom to top
                    GradientStop { position: 0; color: edge.at("right", 1) }
                    GradientStop { position: 0.5; color: edge.at("right", 0.5) }
                    GradientStop { position: 1; color: edge.at("right", 0) }
                }
            }
        }
    }

    Timer {
        interval: 33
        repeat: true
        running: root.running
        onTriggered: scene.tick()
    }
}
