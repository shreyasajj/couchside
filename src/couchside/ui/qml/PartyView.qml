import QtQuick

// Party mode (one of the Visualizer's modes): just the music. Big lyrics (or the artwork
// when there are none) bounce on the beat over a glow, with colour pulsing along the
// screen's edges; the song sits small in the corner. Only to look at.
Item {
    id: party
    property real u: 1
    property real position: 0
    readonly property bool hasLyrics: app.lyricsEnabled && app.hasLyrics

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
            refWidth: party.width * 1.2   // bigger than the Lyrics tab
            stage: true
            size: "large"
            lines: app.lyricLines
            position: party.position
        }
    }

    // no lyrics: the artwork bounces
    Cover {
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height) * 0.5
        height: width
        radius: 28 * party.u
        visible: !party.hasLyrics
        scale: 1.0 + 0.06 * party.kick
        source: app.artUrl
    }

    Text {
        textFormat: Text.PlainText
        anchors { left: parent.left; bottom: parent.bottom; margins: 64 * party.u }
        width: parent.width * 0.5
        text: [app.title, app.artist].filter(s => s !== "").join(" · ")
        color: Theme.textDim
        font.pixelSize: Theme.body * party.u
        font.weight: Font.DemiBold
        elide: Text.ElideRight
    }
}
