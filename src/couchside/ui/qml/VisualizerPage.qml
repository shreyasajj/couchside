import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import "viz.js" as Viz

// The Visualizer tab: the music drawn full-screen. Modes along the bottom (Left/Right
// change it): Radial Pulse, Flow Lines, Bars, and Party (lyrics and edge lights). Top
// left: where the beat comes from (OK picks another source) and how hard it hits
// (Left/Right). After a few seconds without a key the controls and the top bar fade
// away; the next key only brings them back.
FocusScope {
    id: page
    property real u: 1
    property var sheet: null
    property real position: 0
    property real topInset: 104 * u
    property bool active: true           // the app is in front
    property bool chromeHidden: false    // the shell hides the top bar with it

    readonly property var modes: [{ id: "radial", label: "Radial Pulse" }, { id: "flow", label: "Flow Lines" },
                                  { id: "bars", label: "Bars" }, { id: "party", label: "Party" }]
    readonly property bool party: app.visualizerMode === "party"

    function modeButton() {
        for (var i = 0; i < modeRepeater.count; i++)
            if (modeRepeater.itemAt(i).mode === app.visualizerMode) return modeRepeater.itemAt(i)
        return modeRepeater.itemAt(0)
    }
    function focusDefault() { reveal(); var b = modeButton(); if (b) b.forceActiveFocus() }
    Component.onCompleted: { app.loadAudioDevices(); focusDefault() }

    // --- fading the controls away ----------------------------------------------------------
    property Item hiddenFrom: null   // what had focus when the controls went away
    function poke() { idle.restart() }
    function reveal() {
        chromeHidden = false
        idle.restart()
    }
    Timer {
        id: idle
        interval: 4000
        running: true
        // only while the remote is on this screen's controls (not on the top bar, not in a sheet)
        onTriggered: {
            var item = page.Window.activeFocusItem
            if (!page.activeFocus || item === page || (page.sheet && page.sheet.visible)) return
            page.hiddenFrom = item
            page.chromeHidden = true
            page.forceActiveFocus()   // the next key lands here: it only brings the controls back
        }
    }
    Connections {
        target: page.Window.window
        function onActiveFocusItemChanged() { if (!page.chromeHidden) page.poke() }
    }
    Keys.onPressed: (event) => {
        if (!chromeHidden) return
        reveal()
        if (hiddenFrom && hiddenFrom.visible) hiddenFrom.forceActiveFocus()
        else focusDefault()
        event.accepted = true
    }
    // Back with the controls away: just leave (the shell goes to Now Playing).
    function handleBack() { return false }

    Rectangle { anchors.fill: parent; color: "#050507" }

    // --- the pictures: ordinary items the graphics card draws, moved 30 times a second ---
    // Everything is laid out for 1920 x 1080 and scaled to the screen. One timer reads the
    // music (level, beat, spectrum) and sets a handful of numbers; nothing is painted in
    // software.
    Item {
        id: scene
        visible: !page.party
        width: 1920
        height: 1080
        scale: page.width / width
        transformOrigin: Item.TopLeft

        readonly property string mode: app.visualizerMode
        property real energy: 0
        property real beat: 0          // 0..intensity: this frame's hit
        property real level: 0
        property var bars: Viz.zeros()
        property real t: 0
        property real spin: 0
        property var rings: []
        property var flow: []          // five ribbons, each a list of points
        property real prevBeat: 0
        property double last: 0
        readonly property color c1: Theme.a1
        readonly property color c2: Theme.a2
        function blend(amount) { var c = Viz.mix(c1, c2, amount); return Qt.rgba(c.r, c.g, c.b, 1) }

        function tick() {
            var now = Date.now() / 1000
            var dt = last > 0 ? Math.min(0.1, now - last) : 0.033
            last = now
            var a = Viz.frame(app.vizEnergy, app.vizBeat, app.visualizerIntensity, app.spectrum)
            energy = a.energy
            beat = a.beat
            level = a.level
            t += dt
            if (mode === "bars") {
                bars = a.bars
            } else if (mode === "flow") {
                var lines = []
                for (var i = 0; i < 5; i++) {
                    var pts = Viz.flowPoints(i, t, level, energy, width, height, 32)
                    lines.push(pts.map(function(p) { return Qt.point(p.x, p.y) }))
                }
                flow = lines
            } else {
                spin += (0.12 + energy * 1.3) * dt
                rings = Viz.stepRings(rings, beat, prevBeat, dt)
            }
            prevBeat = beat
        }

        // Radial Pulse: turning spokes, an orb that swells, a ring sent out on every beat.
        Item {
            visible: scene.mode !== "flow" && scene.mode !== "bars"
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
            Shape {   // the orb: drawn once, only its size changes
                id: orb
                readonly property real size: Viz.orbRadius(scene.level) * 1.7
                width: 200
                height: 200
                x: -100
                y: -100
                scale: size / 100
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: "transparent"
                    fillGradient: RadialGradient {
                        centerX: 100; centerY: 100; centerRadius: 100
                        focalX: 100; focalY: 100
                        GradientStop { position: 0; color: Theme.tint(scene.c2, 0.95) }
                        GradientStop { position: 0.4; color: Theme.tint(scene.c1, 0.78) }
                        GradientStop { position: 1; color: Theme.tint(scene.c1, 0) }
                    }
                    PathAngleArc { centerX: 100; centerY: 100; radiusX: 100; radiusY: 100; startAngle: 0; sweepAngle: 360 }
                }
            }
            Rectangle {   // its bright heart
                width: Viz.orbRadius(scene.level) * 0.64
                height: width
                x: -width / 2
                y: -height / 2
                radius: width / 2
                color: "#ebffffff"
                antialiasing: true
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
    }
    Timer {
        interval: 33
        repeat: true
        running: page.visible && page.active && !page.party
        onTriggered: scene.tick()
    }

    PartyView {
        anchors.fill: parent
        visible: page.party
        u: page.u
        position: page.position
    }

    Text {
        textFormat: Text.PlainText
        anchors { horizontalCenter: parent.horizontalCenter; bottom: modeBar.top; bottomMargin: 36 * page.u }
        visible: !app.isPlaying && !page.chromeHidden
        text: app.title === "" ? "Play something to see it move" : "Paused — press play to see it move"
        color: Theme.textDim
        font.pixelSize: Theme.body * page.u
        font.weight: Font.DemiBold
    }

    // --- top left: the beat's source and strength -------------------------------------------
    Column {
        id: beatControls
        anchors { left: parent.left; top: parent.top; leftMargin: Theme.margin * page.u; topMargin: page.topInset + 24 * page.u }
        spacing: 14 * page.u
        opacity: page.chromeHidden ? 0 : 1
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.fadeMs } }

        Chip {
            id: sourceChip
            objectName: "sourceChip"
            u: page.u
            dot: true
            dotColor: app.isPlaying ? Theme.a1 : Theme.textFaint
            active: app.isPlaying
            maxTextWidth: 520 * page.u
            text: app.beatSourceLabel
            Accessible.name: "Beat source: " + text
            KeyNavigation.down: beatChip
            onClicked: page.sheet.open("Listen for the beat on", app.beatSources.map(function(s) {
                return { id: s.id, label: s.label, section: s.section, checked: s.current }
            }), sourceChip, function(id) { app.setBeatSource(id) })
        }
        FocusScope {   // how hard a beat hits: Left/Right
            id: beatChip
            objectName: "beatChip"
            width: beatRow.width + 52 * page.u
            height: 62 * page.u
            activeFocusOnTab: true
            function step(delta) { app.visualizerIntensity = app.visualizerIntensity + delta; page.poke() }
            Keys.onLeftPressed: step(-0.05)
            Keys.onRightPressed: step(0.05)
            Keys.onUpPressed: sourceChip.forceActiveFocus()
            Keys.onDownPressed: { var b = page.modeButton(); if (b) b.forceActiveFocus() }
            Rectangle {
                anchors.fill: parent
                radius: height / 2
                color: "#800a0a10"
                border.width: Math.max(1, page.u)
                border.color: Theme.border
            }
            FocusRing { anchors.fill: parent; u: page.u; radius: height / 2; shown: beatChip.activeFocus }
            Row {
                id: beatRow
                anchors.centerIn: parent
                spacing: 18 * page.u
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    textFormat: Text.PlainText
                    text: "BEAT"
                    color: Theme.textDim
                    font.pixelSize: Theme.label * page.u
                    font.weight: Font.ExtraBold
                    font.letterSpacing: 3 * page.u
                }
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 210 * page.u
                    height: 8 * page.u
                    radius: height / 2
                    color: "#29ffffff"
                    GradientFill {
                        width: parent.width * app.visualizerIntensity / 2.4
                        height: parent.height
                        radius: height / 2
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    textFormat: Text.PlainText
                    width: 64 * page.u
                    text: app.visualizerIntensity.toFixed(2)
                    color: Theme.text
                    font.pixelSize: Theme.label * page.u
                    font.weight: Font.Bold
                    font.features: { "tnum": 1 }
                }
            }
        }
    }

    // --- bottom: the modes -----------------------------------------------------------------
    Rectangle {
        id: modeBar
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 48 * page.u }
        width: modeRow.width + 24 * page.u
        height: modeRow.height + 24 * page.u
        radius: height / 2
        color: "#8c0a0a10"
        border.width: Math.max(1, page.u)
        border.color: Theme.border
        opacity: page.chromeHidden ? 0 : 1
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.fadeMs } }

        Row {
            id: modeRow
            anchors.centerIn: parent
            spacing: 12 * page.u
            Repeater {
                id: modeRepeater
                model: page.modes
                delegate: PillButton {
                    id: pill
                    required property var modelData
                    required property int index
                    readonly property string mode: modelData.id
                    objectName: "mode-" + mode
                    u: page.u
                    text: modelData.label
                    strong: app.visualizerMode === mode
                    font.pixelSize: Theme.label * page.u
                    topPadding: 14 * page.u
                    bottomPadding: 14 * page.u
                    leftPadding: 32 * page.u
                    rightPadding: 32 * page.u
                    // moving onto a mode chooses it: Left/Right change the picture at once
                    onActiveFocusChanged: if (activeFocus) app.visualizerMode = mode
                    onClicked: app.visualizerMode = mode
                    Keys.onLeftPressed: if (index > 0) modeRepeater.itemAt(index - 1).forceActiveFocus()
                    Keys.onRightPressed: if (index < modeRepeater.count - 1) modeRepeater.itemAt(index + 1).forceActiveFocus()
                    Keys.onUpPressed: beatChip.forceActiveFocus()
                }
            }
        }
    }
}
