import QtQuick
import "queue.js" as Queue

// Party mode (one of the Visualizer's modes): just the music, laid out like Now Playing
// with its lyrics showing. The song floats small in the top-left corner, the words fill
// the middle and bounce on the beat over a glow, and Up Next sits on the right. Without
// lyrics the artwork bounces in the middle instead. The edge lights behind it are the
// Visualizer's (Edge Lights). Only to look at.
Item {
    id: party
    property real u: 1
    property real position: 0
    property real topInset: 104 * u
    property real qrBottom: 0           // where the guest QR card ends (0: not showing)
    property bool running: true         // on screen, app in front
    property bool cardShown: true       // the Visualizer's own controls sit in that corner
    readonly property bool hasLyrics: app.lyricsEnabled && app.hasLyrics

    // the music's pulse (level + a swell on each beat), 0..1; no animations (see BeatGlow)
    readonly property real kick: visible ? app.audioPulse : 0

    readonly property var upcoming: Queue.upcoming(app.queueRows,
        { title: app.nextTitle, artist: app.nextArtist, imageUrl: app.nextArtUrl }, function(s) { return app.formatTime(s) })

    BeatGlow {
        anchors.centerIn: words
        width: parent.width * 0.7
        height: parent.height * 0.85
        pulse: party.kick
        baseColour: app.partyLights ? Qt.hsla(party.visible ? app.beatHue : 0.55, 0.8, 0.5, 1)  // with the edges
                                    : app.backgroundColour
        strength: 1.5
    }

    SongCard {
        id: card
        objectName: "partyCard"
        u: party.u
        visible: party.hasLyrics && opacity > 0
        opacity: party.cardShown ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.fadeMs } }
        running: party.running
        x: Theme.margin * party.u
        y: party.topInset + 24 * party.u
        width: Math.min(implicitWidth, upNext.x - x - 40 * party.u)
    }

    UpNext {
        id: upNext
        objectName: "partyUpNext"
        u: party.u
        activeFocusOnTab: false
        anchors { right: parent.right; rightMargin: 48 * party.u }
        y: party.qrBottom > 0 ? party.qrBottom + 16 * party.u : party.topInset + 20 * party.u
        rows: party.upcoming
        maxRows: party.qrBottom > 0 ? 3 : 4
    }

    // the words: between the corner card and Up Next, as large as Now Playing's
    Item {
        id: words
        objectName: "partyWords"
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom
                  leftMargin: Theme.margin * party.u; topMargin: party.topInset + card.height + 48 * party.u
                  bottomMargin: 110 * party.u }
        width: (upNext.visible ? upNext.x - 48 * party.u : parent.width - Theme.margin * party.u) - x
        visible: party.hasLyrics
        scale: 1.0 + 0.03 * party.kick
        LyricsView {
            anchors.fill: parent
            u: party.u
            refWidth: party.width
            stage: true
            size: app.lyricsSize
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
        visible: !party.hasLyrics
        text: [app.title, app.artist].filter(s => s !== "").join(" · ")
        color: Theme.textDim
        font.pixelSize: Theme.body * party.u
        font.weight: Font.DemiBold
        elide: Text.ElideRight
    }
}
