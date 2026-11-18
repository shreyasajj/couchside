import QtQuick
import QtQuick.Layouts
import "typing.js" as Typing
import "queue.js" as Queue

// Now Playing: blurred artwork behind, the cover in the middle, then the song, its
// progress and one row of controls. Up Next sits top-right; the guest QR (in the top bar)
// takes the bottom-right corner. The Lyrics button moves the song up into the top-left
// corner (small, floating) and puts the words in the middle, with the visualizer moving
// behind them; Up Next and the controls stay. Party hides the top bar and the buttons and
// keeps the music: the song, the words, Up Next, the progress bar and the QR, over the
// visualizer. Any key (or Back) brings the controls back; media keys keep working.
FocusScope {
    id: page
    property real u: 1
    property real position: 0       // seconds into the song (the shell ticks it)
    property real topInset: 104 * u // the top bar
    property real qrTop: 0          // where the guest QR card starts, bottom-right (0: not showing)
    property bool partyMode: false
    property bool guestOn: app.guestMode
    readonly property bool chromeHidden: partyMode   // the shell hides the top bar with it
    property bool active: true      // the app is in front
    property var sheet: null
    signal openPage(string name)
    signal openVolume(Item opener)
    signal typed(string text)

    function enterParty() { partyMode = true; page.forceActiveFocus() }
    function leaveParty() { partyMode = false; partyButton.forceActiveFocus() }
    function handleBack() { if (!partyMode) return false; leaveParty(); return true }
    onVisibleChanged: if (!visible) partyMode = false

    // letters from a keyboard remote open Search with them; in Party any key brings the
    // controls back (and does nothing else)
    Keys.onPressed: (event) => {
        if (partyMode) { leaveParty(); event.accepted = true; return }
        var t = Typing.typed(event)
        if (t) { page.typed(t); event.accepted = true }
    }

    readonly property bool hasMedia: app.title !== ""

    function focusDefault() { playButton.forceActiveFocus() }

    // --- lyrics in place of the cover ------------------------------------------------------
    readonly property bool showLyrics: app.lyricsShown && app.lyricsEnabled && hasMedia
    // the shell listens for this: the visualizer behind the words, and in Party
    // (none when the picture is Off: the blurred cover instead)
    readonly property bool vizBehind: app.visualizerMode !== "off"
                                      && ((showLyrics && app.lyricsVisualizer) || (partyMode && app.visualizerEnabled))
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
    readonly property var upcoming: Queue.upcoming(app.queueRows,
        { title: app.nextTitle, artist: app.nextArtist, imageUrl: app.nextArtUrl }, function(s) { return app.formatTime(s) })

    // behind the words and in Party: the visualizer picture chosen on its screen. Its
    // pictures are dimmed so the words stay the brightest thing, and darker still under the
    // controls; the edge lights keep their full strength.
    Loader {
        anchors.fill: parent
        z: -1
        active: page.vizBehind
        sourceComponent: Item {
            Rectangle { anchors.fill: parent; color: "#050507" }
            VizScene {
                objectName: "lyricsViz"
                anchors.fill: parent
                dim: 0.6
                shade: true
                mode: app.visualizerMode
                running: page.visible && page.active
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
        id: statusLine
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

    // --- the cover (it makes way for the words) ------------------------------------------
    Item {
        id: artCard
        readonly property real topY: page.topInset + 28 * page.u
        readonly property real side: Math.max(120 * page.u, Math.min(560 * page.u, block.y - topY - 36 * page.u))
        width: side
        height: side
        x: (parent.width - width) / 2
        y: topY + (block.y - topY - 36 * page.u - side) / 2
        opacity: page.showLyrics ? 0 : 1
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 220 } }
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
            radius: 28 * page.u
            source: app.artUrl
        }
    }

    // --- with the lyrics: the song, small and floating, in the top-left corner -------------
    SongCard {
        id: songCard
        objectName: "songCard"
        u: page.u
        opacity: page.showLyrics ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 220 } }
        running: page.visible && page.active
        x: Theme.margin * page.u
        y: statusLine.visible ? statusLine.y + statusLine.height + 16 * page.u : page.topInset + 24 * page.u
        width: Math.min(implicitWidth, (upNext.visible ? upNext.x : page.width) - x - 40 * page.u)
    }

    // --- the words: centred under the corner card, clear of Up Next, above the controls --
    Item {
        id: words
        objectName: "words"
        // Up Next is one song while the words show, so the words go under it and the corner
        // card and take the screen's width; if Up Next sits low (under the guest QR) they keep
        // clear of it beside it instead, as much room on the left as it takes on the right
        readonly property real cardBottom: songCard.y + songCard.height
        readonly property bool under: !upNext.visible || upNext.y + upNext.height < cardBottom + 120 * page.u
        // above the controls, and above the guest QR in the bottom corner
        anchors { horizontalCenter: parent.horizontalCenter; bottom: block.top
                  bottomMargin: 20 * page.u + (page.qrTop > 0 ? Math.max(0, block.y - page.qrTop + 16 * page.u) : 0) }
        anchors.top: parent.top
        anchors.topMargin: (under && upNext.visible ? Math.max(cardBottom, upNext.y + upNext.height) : cardBottom) + 32 * page.u
        width: parent.width - 2 * (under ? Theme.margin * page.u : parent.width - upNext.x + 48 * page.u)
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

    // --- up next (top-right) ---------------------------------------------------------------
    UpNext {
        id: upNext
        objectName: "upNext"
        u: page.u
        anchors { right: parent.right; rightMargin: 48 * page.u }
        y: page.topInset + 20 * page.u
        rows: page.upcoming
        visible: rows.length > 0
        maxRows: page.showLyrics ? 1 : 4
        onActivated: page.openPage("queue")
        Keys.onDownPressed: partyButton.forceActiveFocus()
        Keys.onLeftPressed: playButton.forceActiveFocus()
    }

    // --- the song, its progress and the controls ---------------------------------------
    Column {
        id: block
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 50 * page.u }
        width: Math.min(1360 * page.u, parent.width - 2 * Theme.margin * page.u)

        // the song's name (in the corner card instead while the lyrics show)
        Text {
            textFormat: Text.PlainText
            width: parent.width
            visible: !page.showLyrics
            text: page.hasMedia ? app.title : (app.hasLocalPlayer ? "Nothing playing" : "")
            color: Theme.text
            font.pixelSize: Theme.display * page.u
            font.weight: Font.ExtraBold
            font.letterSpacing: -1.5 * page.u
            elide: Text.ElideRight
        }
        Text {
            textFormat: Text.PlainText
            width: parent.width
            visible: !page.showLyrics
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
            width: parent.width
            topPadding: 6 * page.u
            visible: page.hasMedia && app.nowPlayingCredit !== "" && !page.showLyrics
            text: "Added by " + app.nowPlayingCredit
            color: Theme.a1
            font.pixelSize: Theme.label * page.u
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Item { width: 1; height: 30 * page.u }
        TrackProgress {
            objectName: "progress"
            width: parent.width
            u: page.u
            opacity: page.hasMedia ? 1 : 0
            position: page.position
            duration: app.duration
        }
        Item { width: 1; height: 40 * page.u; visible: controls.visible }   // room for the focused button's name

        // Shuffle, repeat and guest mode on the left, the transport in the middle, volume,
        // lyrics, the visualizer and party on the right. Left/Right walks through all of them in order.
        // Party hides them.
        Item {
            id: controls
            width: parent.width
            height: playButton.height
            visible: !page.partyMode

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
                    KeyNavigation.right: guestButton
                    onClicked: app.cycleRepeat()
                }
                FocusButton {   // off: turns guest mode on; on: the guest list (turned off there)
                    id: guestButton
                    objectName: "guestButton"
                    u: page.u
                    iconName: "qr"
                    text: page.guestOn ? "Guests" : "Guest mode"
                    active: page.guestOn
                    KeyNavigation.left: repeatButton
                    KeyNavigation.right: prevButton
                    onClicked: page.guestOn ? page.openPage("guests") : app.toggleGuestMode()
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
                    KeyNavigation.left: guestButton
                    KeyNavigation.right: playButton
                    onClicked: app.previous()
                }
                FocusButton {
                    id: playButton
                    objectName: "playButton"
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
                    KeyNavigation.right: volumeButton.visible ? volumeButton : (lyricsButton.visible ? lyricsButton : vizButton)
                    onClicked: app.next()
                }
            }

            Row {
                anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                spacing: 16 * page.u
                FocusButton {
                    id: volumeButton
                    objectName: "volumeButton"
                    anchors.verticalCenter: parent.verticalCenter
                    u: page.u
                    visible: app.hasVolume
                    iconName: app.volume === 0 ? "volume-muted"
                              : app.volume < 34 ? "volume-none"
                              : app.volume < 67 ? "volume-low" : "volume-high"
                    text: "Volume " + app.volume
                    KeyNavigation.left: nextButton
                    KeyNavigation.right: lyricsButton.visible ? lyricsButton : vizButton
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
                    KeyNavigation.right: vizButton
                    Keys.onUpPressed: (event) => { if (upNext.visible) upNext.forceActiveFocus(); else event.accepted = false }
                    onClicked: app.lyricsShown = !app.lyricsShown
                }
                FocusButton {
                    id: vizButton
                    objectName: "visualizerButton"
                    anchors.verticalCenter: parent.verticalCenter
                    u: page.u
                    iconName: "visualizer"
                    text: "Visualizer"
                    KeyNavigation.left: lyricsButton.visible ? lyricsButton : (volumeButton.visible ? volumeButton : nextButton)
                    KeyNavigation.right: partyButton
                    Keys.onUpPressed: (event) => { if (upNext.visible) upNext.forceActiveFocus(); else event.accepted = false }
                    onClicked: page.openPage("visualizer")
                }
                FocusButton {
                    id: partyButton
                    objectName: "partyButton"
                    anchors.verticalCenter: parent.verticalCenter
                    u: page.u
                    iconName: "party"
                    text: "Party"
                    KeyNavigation.left: vizButton
                    Keys.onRightPressed: (event) => { if (upNext.visible) upNext.forceActiveFocus() }
                    Keys.onUpPressed: (event) => { if (upNext.visible) upNext.forceActiveFocus(); else event.accepted = false }
                    onClicked: page.enterParty()
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
