import QtQuick
import QtQuick.Controls as QQC2

// Party mode: no controls, just the music. Big lyrics (or the artwork when there are none)
// bounce on the beat over a glow, with colour pulsing along the screen's edges; the song sits small in the corner. Back leaves (Main's
// shortcut); media keys keep working; every other key is swallowed so nothing hidden reacts.
FocusScope {
    id: party
    property real u: 1
    property real position: 0
    readonly property bool hasLyrics: app.lyricsEnabled && app.hasLyrics

    Keys.onPressed: (event) => { event.accepted = true }

    // the music's pulse (level + a swell on each beat), 0..1; no animations (see BeatGlow)
    readonly property real kick: visible ? app.audioPulse : 0

    // colour to the very edges of the screen: lights that copy the screen dance along
    EdgeLights {
        anchors.fill: parent
        visible: app.partyLights
        pulse: party.visible && visible ? app.lightPulse : 0   // slower than the glow: see the controller
        hue: party.visible ? app.beatHue : 0.55
    }

    BeatGlow {
        anchors.centerIn: parent
        width: parent.width * 0.75
        height: parent.height * 0.9
        pulse: party.kick
        baseColour: app.partyLights ? Qt.hsla(party.visible ? app.beatHue : 0.55, 0.8, 0.5, 1)  // with the edges
                                    : app.backgroundColour
        strength: 1.5
    }

    // lyrics, big and centred
    Item {
        anchors.centerIn: parent
        width: parent.width * 0.84
        height: parent.height * 0.72
        visible: party.hasLyrics
        scale: 1.0 + 0.04 * party.kick
        LyricsView {
            anchors.fill: parent
            u: party.u
            refWidth: party.width * 1.25   // bigger than the "large" preset on Now Playing
            size: "large"
            lines: app.lyricLines
            position: party.position
        }
    }

    // no lyrics: the artwork bounces
    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height) * 0.5
        height: width
        radius: 24 * party.u
        color: "#2b2163"
        clip: true
        visible: !party.hasLyrics
        scale: 1.0 + 0.06 * party.kick
        CrossfadeImage {
            anchors.fill: parent
            source: app.artUrl
            sourceSize: Qt.size(width, height)
        }
    }

    QQC2.Label {
        textFormat: Text.PlainText
        anchors { left: parent.left; bottom: parent.bottom; margins: 64 * party.u }
        width: parent.width * 0.6
        text: [app.title, app.artist].filter(s => s !== "").join(" · ")
        color: "#ffffff"
        opacity: 0.75
        font.pixelSize: 32 * party.u
        font.weight: Font.DemiBold
        elide: Text.ElideRight
    }

    // how to get out, shown for a moment when party mode starts
    QQC2.Label {
        id: hint
        textFormat: Text.PlainText
        anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: 48 * party.u }  // clear of the title
        text: "Party mode · Back to leave"
        color: "#ffffff"
        font.pixelSize: 28 * party.u
        opacity: 0
        Behavior on opacity { NumberAnimation { duration: 600 } }
    }
    Timer { id: hintTimer; interval: 3000; onTriggered: hint.opacity = 0 }
    onVisibleChanged: if (visible) { hint.opacity = 0.8; hintTimer.restart() }
}
