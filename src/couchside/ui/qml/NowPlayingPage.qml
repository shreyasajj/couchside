import QtQuick
import QtQuick.Layouts
import "typing.js" as Typing

// Now Playing: blurred artwork behind, the cover in the middle, then the song, its
// progress and one row of controls. Up Next sits top-right (under the guest QR when that
// is showing). The Lyrics button moves the cover down beside the title and puts the words
// where it was, with the visualizer moving behind them.
FocusScope {
    id: page
    property real u: 1
    property real position: 0       // seconds into the song (the shell ticks it)
    property real topInset: 104 * u // the top bar
    property real qrBottom: 0       // where the guest QR card ends (0: not showing)
    property bool active: true      // the app is in front
    property var sheet: null
    signal openPage(string name)
    signal openVolume(Item opener)
    signal typed(string text)

    // letters from a keyboard remote open Search with them
    Keys.onPressed: (event) => {
        var t = Typing.typed(event)
        if (t) { page.typed(t); event.accepted = true }
    }

    readonly property bool hasMedia: app.title !== ""

    function focusDefault() { playButton.forceActiveFocus() }

    // --- lyrics in place of the cover ------------------------------------------------------
    readonly property bool showLyrics: app.lyricsShown && app.lyricsEnabled && hasMedia
    readonly property bool vizBehind: showLyrics && app.lyricsVisualizer   // the shell listens for this
    // Keep the last song's words for a moment while the next song's are looked up (cache
    // hits take one event-loop turn, LRCLIB a second or two); give up after 1.5 s.
    property bool wordsShown: false
    function updateWords() {
        if (app.hasLyrics) { wordsShown = true; hold.stop() }
        else if (app.lyricsPending) { if (wordsShown && !hold.running) hold.start() }
        else { wordsShown = false; hold.stop() }
    }
    Timer { id: hold; interval: 1500; onTriggered: if (!app.hasLyrics) page.wordsShown = false }
    Connections { target: app; function onLyricsChanged() { page.updateWords() } }
    Component.onCompleted: updateWords()

    // the songs after the one playing, for the Up Next card
    readonly property var upcoming: {
        var rows = app.queueRows, at = -1
        for (var i = 0; i < rows.length; i++) if (rows[i].current) { at = i; break }
        var out = []
        for (var j = at + 1; j < rows.length; j++)
            out.push({ title: rows[j].title, subtitle: rows[j].subtitle, imageUrl: rows[j].imageUrl,
                       trailing: rows[j].duration > 0 ? app.formatTime(rows[j].duration) : "" })
        if (out.length === 0 && app.nextTitle !== "")   // the queue isn't loaded yet
            out.push({ title: app.nextTitle, subtitle: app.nextArtist, imageUrl: app.nextArtUrl, trailing: "" })
        return out
    }

    // behind the words: the visualizer (Edge Lights stands in for Party here), dimmed so
    // the words stay the brightest thing, and darker still under the controls
    Loader {
        anchors.fill: parent
        z: -1
        active: page.vizBehind
        sourceComponent: Item {
            Rectangle { anchors.fill: parent; color: "#050507" }
            VizScene {
                anchors.fill: parent
                opacity: 0.6
                mode: app.visualizerMode === "party" ? "edge" : app.visualizerMode
                running: page.visible && page.active
            }
            Rectangle {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                height: parent.height * 0.45
                gradient: Gradient {
                    GradientStop { position: 0; color: "#00050507" }
                    GradientStop { position: 0.7; color: "#cc050507" }
                }
            }
        }
    }
    ArtBackground {
        anchors.fill: parent
        visible: !page.vizBehind
        source: app.artUrl  // same URL as the cover: one download; blurred at 384 px anyway
        baseColour: app.backgroundColour
    }

    // --- status (reconnecting, no speaker, …) ----------------------------------------
    Text {
        textFormat: Text.PlainText
        anchors { left: parent.left; top: parent.top; leftMargin: Theme.margin * page.u; topMargin: page.topInset + 12 * page.u }
        width: parent.width * 0.3
        visible: text !== ""
        text: app.statusText
        color: Theme.warn
        font.pixelSize: Theme.label * page.u
        font.weight: Font.DemiBold
        wrapMode: Text.WordWrap
    }

    // --- the cover -----------------------------------------------------------------------
    Item {
        id: artCard
        readonly property real topY: page.topInset + 28 * page.u
        readonly property real big: Math.max(120 * page.u, Math.min(560 * page.u, block.y - topY - 36 * page.u))
        readonly property real small: 150 * page.u   // beside the title while the words show
        readonly property real side: page.showLyrics ? small : big
        width: side
        height: side
        x: page.showLyrics ? block.x : (parent.width - width) / 2
        y: page.showLyrics ? block.y : topY + (block.y - topY - 36 * page.u - big) / 2
        Behavior on x { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
        Behavior on width { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
        // the beat: a slight swell (a transform only: nothing is drawn again)
        scale: app.visualizerEnabled && !page.showLyrics ? 1 + 0.028 * app.audioPulse : 1

        BeatGlow {
            anchors.centerIn: parent
            width: parent.width * 2.0   // mostly hidden by the cover: the halo is what shows
            height: width
            strength: 1.2
            visible: app.visualizerEnabled && !page.showLyrics
            pulse: visible ? app.audioPulse : 0  // hidden: no binding work
            baseColour: Theme.a2
        }
        Cover {
            anchors.fill: parent
            radius: (page.showLyrics ? 16 : 28) * page.u
            source: app.artUrl
        }
    }

    // --- the words, where the cover was -------------------------------------------------
    Item {
        id: words
        objectName: "words"
        anchors { left: parent.left; right: parent.right; top: parent.top; bottom: block.top
                  topMargin: page.topInset; bottomMargin: 20 * page.u
                  leftMargin: 180 * page.u; rightMargin: page.qrBottom > 0 ? 420 * page.u : 180 * page.u }
        visible: page.showLyrics
        LyricsView {
            anchors.fill: parent
            visible: page.wordsShown
            u: page.u
            refWidth: page.width
            stage: true
            size: app.lyricsSize
            lines: app.lyricLines
            position: page.position
        }
        Text {
            textFormat: Text.PlainText
            anchors.centerIn: parent
            visible: !page.wordsShown
            text: app.lyricsPending ? "Looking for lyrics…" : "No lyrics for this song"
            color: Theme.textDim
            font.pixelSize: Theme.heading * page.u
            font.weight: Font.Bold
        }
    }

    // --- up next (top-right; under the guest QR when that is showing) ------------------
    UpNext {
        id: upNext
        u: page.u
        anchors { right: parent.right; rightMargin: 48 * page.u }
        y: page.qrBottom > 0 ? page.qrBottom + 16 * page.u : page.topInset + 20 * page.u
        rows: page.upcoming
        visible: rows.length > 0 && !page.showLyrics   // the words take the whole width
        maxRows: page.qrBottom > 0 ? 3 : 4
        onActivated: page.openPage("queue")
        Keys.onDownPressed: partyButton.forceActiveFocus()
        Keys.onLeftPressed: playButton.forceActiveFocus()
    }

    // --- the song, its progress and the controls ---------------------------------------
    Column {
        id: block
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 50 * page.u }
        width: Math.min(1360 * page.u, parent.width - 2 * Theme.margin * page.u)

        readonly property real inset: page.showLyrics ? artCard.small + 32 * page.u : 0
        Text {
            textFormat: Text.PlainText
            x: block.inset
            width: parent.width - block.inset
            text: page.hasMedia ? app.title : (app.hasLocalPlayer ? "Nothing playing" : "")
            color: Theme.text
            font.pixelSize: (page.showLyrics ? 60 : Theme.display) * page.u
            font.weight: Font.ExtraBold
            font.letterSpacing: -1.5 * page.u
            elide: Text.ElideRight
        }
        Text {
            textFormat: Text.PlainText
            x: block.inset
            width: parent.width - block.inset
            topPadding: 4 * page.u
            text: page.hasMedia ? [app.artist, app.album].filter(s => s !== "").join(" — ")
                                : "Play something from Music Assistant"
            color: Theme.textDim
            font.pixelSize: Theme.subtitle * page.u
            font.weight: Font.Medium
            elide: Text.ElideRight
        }
        Text {
            textFormat: Text.PlainText
            x: block.inset
            width: parent.width - block.inset
            topPadding: 6 * page.u
            visible: page.hasMedia && app.nowPlayingCredit !== ""
            text: "Added by " + app.nowPlayingCredit
            color: Theme.a1
            font.pixelSize: Theme.label * page.u
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Item {   // the small cover stands beside the lines above: never end before it does
            id: gap
            width: 1
            height: Math.max(30 * page.u, page.showLyrics ? artCard.small + 30 * page.u - gap.y : 0)
        }
        TrackProgress {
            width: parent.width
            u: page.u
            opacity: page.hasMedia ? 1 : 0
            position: page.position
            duration: app.duration
        }
        Item { width: 1; height: 40 * page.u }   // room for the focused button's name

        // Shuffle and repeat on the left, the transport in the middle, volume and party
        // on the right. Left/Right walks through all of them in that order.
        Item {
            width: parent.width
            height: playButton.height

            Row {
                anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                spacing: 28 * page.u
                FocusButton {
                    id: shuffleButton
                    u: page.u
                    iconName: "shuffle"
                    text: app.shuffle ? "Shuffle on" : "Shuffle off"
                    active: app.shuffle
                    KeyNavigation.right: repeatButton
                    onClicked: app.toggleShuffle()
                }
                FocusButton {
                    id: repeatButton
                    u: page.u
                    iconName: app.repeatMode === "one" ? "repeat-one" : "repeat"
                    text: app.repeatMode === "one" ? "Repeat one" : (app.repeatMode === "all" ? "Repeat all" : "Repeat off")
                    active: app.repeatMode !== "off"
                    KeyNavigation.left: shuffleButton
                    KeyNavigation.right: prevButton
                    onClicked: app.cycleRepeat()
                }
            }

            Row {
                anchors.centerIn: parent
                spacing: 48 * page.u
                FocusButton {
                    id: prevButton
                    anchors.verticalCenter: parent.verticalCenter
                    u: page.u
                    iconScale: 0.72
                    iconName: "previous"
                    text: "Previous"
                    KeyNavigation.left: repeatButton
                    KeyNavigation.right: playButton
                    onClicked: app.previous()
                }
                FocusButton {
                    id: playButton
                    anchors.verticalCenter: parent.verticalCenter
                    u: page.u
                    primary: true
                    showLabel: false  // the biggest button, and everyone knows it
                    iconName: app.isPlaying ? "pause" : "play"
                    text: app.isPlaying ? "Pause" : "Play"
                    KeyNavigation.left: prevButton
                    KeyNavigation.right: nextButton
                    onClicked: app.playPause()
                }
                FocusButton {
                    id: nextButton
                    anchors.verticalCenter: parent.verticalCenter
                    u: page.u
                    iconScale: 0.72
                    iconName: "next"
                    text: "Next"
                    KeyNavigation.left: playButton
                    KeyNavigation.right: volumeButton.visible ? volumeButton : (lyricsButton.visible ? lyricsButton : partyButton)
                    onClicked: app.next()
                }
            }

            Row {
                anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                spacing: 16 * page.u
                FocusButton {
                    id: volumeButton
                    anchors.verticalCenter: parent.verticalCenter
                    u: page.u
                    visible: app.hasVolume
                    iconName: app.volume === 0 ? "volume-muted"
                              : app.volume < 34 ? "volume-none"
                              : app.volume < 67 ? "volume-low" : "volume-high"
                    text: "Volume " + app.volume
                    KeyNavigation.left: nextButton
                    KeyNavigation.right: lyricsButton.visible ? lyricsButton : partyButton
                    Keys.onUpPressed: (event) => { if (upNext.visible) upNext.forceActiveFocus(); else event.accepted = false }
                    onClicked: page.openVolume(volumeButton)
                }
                Rectangle {  // the level, to look at
                    anchors.verticalCenter: parent.verticalCenter
                    visible: app.hasVolume
                    width: 120 * page.u
                    height: 8 * page.u
                    radius: height / 2
                    color: "#29ffffff"
                    GradientFill {
                        width: parent.width * Math.max(0, Math.min(100, app.volume)) / 100
                        height: parent.height
                        radius: height / 2
                    }
                }
                FocusButton {
                    id: lyricsButton
                    objectName: "lyricsButton"
                    anchors.verticalCenter: parent.verticalCenter
                    u: page.u
                    visible: app.lyricsEnabled
                    iconName: "lyrics"
                    text: app.lyricsShown ? "Hide lyrics" : "Lyrics"
                    active: app.lyricsShown
                    KeyNavigation.left: volumeButton.visible ? volumeButton : nextButton
                    KeyNavigation.right: partyButton
                    Keys.onUpPressed: (event) => { if (upNext.visible) upNext.forceActiveFocus(); else event.accepted = false }
                    onClicked: app.lyricsShown = !app.lyricsShown
                }
                FocusButton {
                    id: partyButton
                    objectName: "visualizerButton"
                    anchors.verticalCenter: parent.verticalCenter
                    u: page.u
                    iconName: "party"
                    text: "Visualizer"
                    KeyNavigation.left: lyricsButton.visible ? lyricsButton : (volumeButton.visible ? volumeButton : nextButton)
                    Keys.onRightPressed: (event) => { if (upNext.visible) upNext.forceActiveFocus() }
                    Keys.onUpPressed: (event) => { if (upNext.visible) upNext.forceActiveFocus(); else event.accepted = false }
                    onClicked: page.openPage("visualizer")
                }
            }
        }
    }

    // If the volume button disappears while focused, keep focus on the row.
    Connections {
        target: volumeButton
        function onVisibleChanged() { if (!volumeButton.visible && page.activeFocus) playButton.forceActiveFocus() }
    }
    Connections {
        target: lyricsButton
        function onVisibleChanged() { if (!lyricsButton.visible && page.activeFocus) playButton.forceActiveFocus() }
    }
}
