import QtQuick

// The Lyrics tab: the song's words filling the screen, the line being sung in the accent
// colour. Without lyrics: the cover and a line saying so. Nothing to operate here; OK
// plays and pauses.
FocusScope {
    id: page
    property real u: 1
    property real position: 0
    property real topInset: 104 * u
    property real qrWidth: 0

    function focusDefault() { forceActiveFocus() }
    Component.onCompleted: { updateShown(); forceActiveFocus() }
    Keys.onReturnPressed: (event) => { if (!event.isAutoRepeat) app.playPause() }
    Keys.onEnterPressed: (event) => { if (!event.isAutoRepeat) app.playPause() }
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Select) { if (!event.isAutoRepeat) app.playPause(); event.accepted = true }
    }

    // Keep the last song's words on screen for a moment while the next song's are looked
    // up (cache hits take one event-loop turn, LRCLIB a second or two) instead of
    // flashing the cover; give up after 1.5 s.
    property bool shown: false
    function updateShown() {
        if (app.hasLyrics) { shown = true; hold.stop() }
        else if (app.lyricsPending) { if (shown && !hold.running) hold.start() }
        else { shown = false; hold.stop() }
    }
    Timer { id: hold; interval: 1500; onTriggered: if (!app.hasLyrics) page.shown = false }
    Connections { target: app; function onLyricsChanged() { page.updateShown() } }

    Rectangle {  // a faint wash of the accent behind the words
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Theme.bg }
            GradientStop { position: 0.45; color: Qt.tint(Theme.bg, Theme.tint(Theme.a1, 0.05)) }
            GradientStop { position: 1.0; color: Theme.bg }
        }
    }

    LyricsView {
        anchors { fill: parent; topMargin: page.topInset; leftMargin: 180 * page.u
                  rightMargin: Math.max(180 * page.u, page.qrWidth); bottomMargin: 96 * page.u }
        visible: page.shown && app.title !== ""
        u: page.u
        refWidth: page.width
        stage: true
        size: app.lyricsSize
        lines: app.lyricLines
        position: page.position
    }

    // --- no lyrics: the cover, and why ---------------------------------------------------
    Column {
        anchors.centerIn: parent
        visible: !page.shown || app.title === ""
        spacing: 36 * page.u
        Cover {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 420 * page.u
            height: width
            radius: 28 * page.u
            source: app.artUrl
        }
        Text {
            textFormat: Text.PlainText
            anchors.horizontalCenter: parent.horizontalCenter
            text: app.title === "" ? "Nothing playing"
                  : app.lyricsPending ? "Looking for lyrics…" : "No lyrics for this song"
            color: Theme.textDim
            font.pixelSize: Theme.heading * page.u
            font.weight: Font.Bold
        }
    }

    // --- which song, small in the corner -------------------------------------------------
    Text {
        textFormat: Text.PlainText
        anchors { left: parent.left; bottom: parent.bottom; leftMargin: Theme.margin * page.u; bottomMargin: 40 * page.u }
        width: parent.width * 0.5
        visible: app.title !== ""
        text: [app.title, app.artist].filter(s => s !== "").join(" · ")
        color: Theme.textFaint
        font.pixelSize: Theme.label * page.u
        font.weight: Font.DemiBold
        elide: Text.ElideRight
    }
}
