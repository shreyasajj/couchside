import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import "typing.js" as Typing

// Now Playing: blurred artwork behind, the cover in the middle, then the song, its
// progress and one row of controls. Up Next sits top-right (under the guest QR when that
// is showing). Lyrics have their own tab.
FocusScope {
    id: page
    property real u: 1
    property real position: 0       // seconds into the song (the shell ticks it)
    property real topInset: 104 * u // the top bar
    property real qrBottom: 0       // where the guest QR card ends (0: not showing)
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

    ArtBackground {
        anchors.fill: parent
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
        readonly property real side: Math.max(120 * page.u, Math.min(560 * page.u, block.y - topY - 36 * page.u))
        width: side
        height: side
        x: (parent.width - width) / 2
        y: topY + (block.y - topY - 36 * page.u - side) / 2
        // the beat: a slight swell (a transform only: nothing is drawn again)
        scale: app.visualizerEnabled ? 1 + 0.028 * app.audioPulse : 1

        BeatGlow {
            anchors.centerIn: parent
            width: parent.width * 2.0   // mostly hidden by the cover: the halo is what shows
            height: width
            strength: 1.2
            visible: app.visualizerEnabled
            pulse: visible ? app.audioPulse : 0  // hidden: no binding work
            baseColour: Theme.a2
        }
        Rectangle {
            id: artMask
            anchors.fill: parent
            radius: 28 * page.u
            color: "#ffffff"
            visible: false
            layer.enabled: true
        }
        Item {
            id: artContent
            anchors.fill: parent
            visible: false
            layer.enabled: true
            Rectangle { anchors.fill: parent; color: "#16161f" }
            Icon {
                anchors.centerIn: parent
                size: parent.width * 0.3
                name: "music"
                color: "#40ffffff"
                visible: !artImage.hasImage
            }
            CrossfadeImage {
                id: artImage
                anchors.fill: parent
                source: app.artUrl
                // decode at the cover's real size: sharp on a 4K TV (the URL serves 1024 px)
                sourceSize: Qt.size(artCard.side, artCard.side)
            }
        }
        MultiEffect {  // rounded corners + soft shadow
            anchors.fill: parent
            source: artContent
            maskEnabled: true
            maskSource: artMask
            maskThresholdMin: 0.5
            maskSpreadAtMin: 1.0
            shadowEnabled: true
            shadowBlur: 1.0
            shadowOpacity: 0.6
            shadowVerticalOffset: 16 * page.u
        }
    }

    // --- up next (top-right; under the guest QR when that is showing) ------------------
    UpNext {
        id: upNext
        u: page.u
        anchors { right: parent.right; rightMargin: 48 * page.u }
        y: page.qrBottom > 0 ? page.qrBottom + 16 * page.u : page.topInset + 20 * page.u
        rows: page.upcoming
        maxRows: page.qrBottom > 0 ? 3 : 4
        onActivated: page.openPage("queue")
        Keys.onDownPressed: partyButton.forceActiveFocus()
        Keys.onLeftPressed: playButton.forceActiveFocus()
    }

    // --- the song, its progress and the controls ---------------------------------------
    Column {
        id: block
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 50 * page.u }
        width: Math.min(1180 * page.u, parent.width - 2 * Theme.margin * page.u)

        Text {
            textFormat: Text.PlainText
            width: parent.width
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
            visible: page.hasMedia && app.nowPlayingCredit !== ""
            text: "Added by " + app.nowPlayingCredit
            color: Theme.a1
            font.pixelSize: Theme.label * page.u
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Item { width: 1; height: 30 * page.u }
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
                    KeyNavigation.right: volumeButton.visible ? volumeButton : partyButton
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
                    KeyNavigation.right: partyButton
                    Keys.onUpPressed: (event) => { if (upNext.visible) upNext.forceActiveFocus(); else event.accepted = false }
                    onClicked: page.openVolume(volumeButton)
                }
                Rectangle {  // the level, to look at
                    anchors.verticalCenter: parent.verticalCenter
                    visible: app.hasVolume
                    width: 150 * page.u
                    height: 8 * page.u
                    radius: height / 2
                    color: "#29ffffff"
                    GradientFill {
                        width: parent.width * Math.max(0, Math.min(100, app.volume)) / 100
                        height: parent.height
                        radius: height / 2
                    }
                }
                Item { width: 12 * page.u; height: 1 }
                FocusButton {
                    id: partyButton
                    anchors.verticalCenter: parent.verticalCenter
                    u: page.u
                    iconName: "party"
                    text: "Party mode"
                    KeyNavigation.left: volumeButton.visible ? volumeButton : nextButton
                    Keys.onRightPressed: (event) => { if (upNext.visible) upNext.forceActiveFocus() }
                    Keys.onUpPressed: (event) => { if (upNext.visible) upNext.forceActiveFocus(); else event.accepted = false }
                    onClicked: { app.visualizerMode = "party"; page.openPage("visualizer") }
                }
            }
        }
    }

    // If the volume button disappears while focused, keep focus on the row.
    Connections {
        target: volumeButton
        function onVisibleChanged() { if (!volumeButton.visible && page.activeFocus) playButton.forceActiveFocus() }
    }
}
