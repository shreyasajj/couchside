import QtQuick
import QtQuick.Layouts
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

    // --- the drawing: a small canvas scaled up, 30 times a second at most --------------------
    Canvas {
        id: canvas
        visible: !page.party
        width: 1280
        height: 720
        scale: page.width / width
        transformOrigin: Item.TopLeft
        smooth: true
        property var st: Viz.newState()
        property double last: 0
        function rgb(c) { return { r: Math.round(c.r * 255), g: Math.round(c.g * 255), b: Math.round(c.b * 255) } }
        onPaint: {
            var ctx = getContext("2d")
            var now = Date.now() / 1000
            var dt = last > 0 ? Math.min(0.1, now - last) : 0.033
            last = now
            st.dt = dt
            st.t += dt
            st.c1 = rgb(Theme.a1)
            st.c2 = rgb(Theme.a2)
            ctx.save()
            ctx.scale(width / 1920, height / 1080)   // the drawings are made for 1920 x 1080
            Viz.draw(app.visualizerMode, ctx, 1920, 1080,
                     Viz.frame(app.vizEnergy, app.vizBeat, app.visualizerIntensity, app.spectrum), st)
            ctx.restore()
        }
    }
    Timer {
        interval: 33
        repeat: true
        running: page.visible && page.active && !page.party
        onTriggered: canvas.requestPaint()
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
