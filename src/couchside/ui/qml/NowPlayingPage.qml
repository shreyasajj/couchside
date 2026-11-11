import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// Now Playing (design "Layout B"). Lyrics arrive in Phase 4; until then this is the
// design's no-lyrics layout: big artwork left, large title, bottom control bar.
Kirigami.Page {
    id: page
    property real u: 1
    signal openSetup()
    signal openPage(string name)

    padding: 0
    globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None
    background: ArtBackground {
        source: app.artUrl  // same URL as the card: one download; blurred at 384 px anyway
        baseColour: app.backgroundColour
    }

    readonly property real margin: 72 * u
    readonly property bool hasMedia: app.title !== ""

    // Focus returns to the control that opened something (Settings) or to play/pause.
    property Item returnFocus: null
    function focusDefault() {
        var target = (returnFocus && returnFocus.visible) ? returnFocus : playButton
        returnFocus = null
        target.forceActiveFocus()
    }
    // Main.goBack() asks the page first; true = handled here.
    function handleBack() {
        if (volumePopup.visible) { volumePopup.close(); return true }
        return false
    }
    function adjustVolume(delta) {
        if (!app.hasVolume) return
        placeVolumePopup()
        volumePopup.flash(delta)
    }
    function placeVolumePopup() {
        var p = volumeButton.mapToItem(page, 0, 0)
        volumePopup.x = Math.max(page.margin, Math.min(page.width - volumePopup.width - page.margin,
                                                       p.x + volumeButton.width / 2 - volumePopup.width / 2))
        volumePopup.y = p.y - volumePopup.height - 32 * page.u
    }
    Component.onCompleted: { focusDefault(); updateLyricsLayout() }

    // --- progress, ticked locally between server updates -------------------------
    property real position: 0
    function updatePosition() {
        var p = app.positionBase
        if (app.isPlaying) p += Date.now() / 1000 - app.positionAt
        p = Math.max(0, p)
        if (app.hasDuration) p = Math.min(app.duration, p)
        position = p
    }
    // Lyrics layout with a short hold: while the next song's lookup runs (cache hits take
    // one event-loop turn, LRCLIB a second or two) keep the lyrics layout instead of
    // flashing the artwork; give up after 1.5 s without lyrics.
    property bool lyricsLayoutOn: false
    readonly property bool showLyrics: lyricsLayoutOn && app.lyricsEnabled && page.hasMedia
    function updateLyricsLayout() {
        if (!app.lyricsEnabled) { lyricsLayoutOn = false; lyricsHold.stop() }
        else if (app.hasLyrics) { lyricsLayoutOn = true; lyricsHold.stop() }
        else if (app.lyricsPending) { if (lyricsLayoutOn && !lyricsHold.running) lyricsHold.start() }
        else { lyricsLayoutOn = false; lyricsHold.stop() }
    }
    Timer { id: lyricsHold; interval: 1500; onTriggered: if (!app.hasLyrics) page.lyricsLayoutOn = false }
    Connections { target: app; function onLyricsChanged() { page.updateLyricsLayout() } }

    Timer {
        interval: page.showLyrics ? 250 : 500  // lyrics need a finer tick than the bar
        repeat: true
        running: app.isPlaying && page.visible && Qt.application.state === Qt.ApplicationActive
        triggeredOnStart: true
        onTriggered: page.updatePosition()
    }
    Connections { target: app; function onChanged() { page.updatePosition() } }

    // --- status ---------------------------------------------------------------------
    QQC2.Label {
        anchors { left: parent.left; top: parent.top; margins: page.margin }
        width: parent.width * 0.6
        visible: text !== ""
        text: app.statusText
        color: "#ffd479"
        font.pixelSize: 32 * page.u
        wrapMode: Text.WordWrap
    }

    // --- artwork + metadata (no-lyrics layout) -------------------------------------
    Item {
        id: content
        opacity: page.showLyrics ? 0 : 1
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 300 } }
        anchors {
            left: parent.left; right: parent.right; top: parent.top; bottom: bar.top
            leftMargin: page.margin; rightMargin: page.margin
            topMargin: 140 * page.u; bottomMargin: 48 * page.u
        }

        RowLayout {
            anchors.fill: parent
            spacing: 64 * page.u

            Item {
                id: artCard
                readonly property real side: Math.min(page.width * 0.33, content.height)
                Layout.preferredWidth: side
                Layout.preferredHeight: side
                Layout.alignment: Qt.AlignVCenter

                Rectangle {
                    id: artFrame
                    anchors.fill: parent
                    radius: 16 * page.u
                    color: "#ffffff"
                    visible: false
                    layer.enabled: true
                }
                Item {
                    id: artContent
                    anchors.fill: parent
                    visible: false
                    layer.enabled: true
                    Rectangle { anchors.fill: parent; color: "#2b2163" }
                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: parent.width * 0.35
                        height: width
                        source: "media-optical-audio"
                        color: "#66ffffff"
                        isMask: true
                        visible: !artImage.hasImage
                    }
                    CrossfadeImage {
                        id: artImage
                        anchors.fill: parent
                        source: app.artUrl
                        // decode at the card's real size: sharp on a 4K TV (URL serves 1024 px)
                        sourceSize: Qt.size(artCard.side, artCard.side)
                    }
                }
                MultiEffect {  // rounded corners + soft shadow
                    anchors.fill: parent
                    source: artContent
                    maskEnabled: true
                    maskSource: artFrame
                    maskThresholdMin: 0.5
                    maskSpreadAtMin: 1.0
                    shadowEnabled: true
                    shadowBlur: 1.0
                    shadowOpacity: 0.6
                    shadowVerticalOffset: 12 * page.u
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                spacing: 12 * page.u

                QQC2.Label {
                    Layout.fillWidth: true
                    text: page.hasMedia ? app.title : (app.hasLocalPlayer ? "Nothing playing" : "")
                    color: "#ffffff"
                    font.pixelSize: page.width * 0.046
                    font.weight: Font.Bold
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                    lineHeight: 1.05
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: text !== ""
                    text: page.hasMedia ? app.artist : "Play something from Music Assistant"
                    color: "#ffffff"
                    opacity: 0.9
                    font.pixelSize: 48 * page.u
                    elide: Text.ElideRight
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: page.hasMedia && text !== ""
                    text: app.album
                    color: "#ffffff"
                    opacity: 0.7
                    font.pixelSize: 36 * page.u
                    elide: Text.ElideRight
                }
            }
        }
    }

    // --- lyrics-forward layout (layout B) -------------------------------------------
    Item {
        id: lyricsLayout
        opacity: page.showLyrics ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 300 } }
        anchors {
            left: parent.left; right: parent.right; top: parent.top; bottom: bar.top
            leftMargin: page.margin; rightMargin: page.margin
            topMargin: page.margin; bottomMargin: 24 * page.u
        }

        RowLayout {  // small sharp artwork, title, artist · album
            id: lyricsHeader
            anchors { left: parent.left; right: parent.right; top: parent.top }
            spacing: 32 * page.u
            Rectangle {
                Layout.preferredWidth: page.width * 0.1
                Layout.preferredHeight: page.width * 0.1
                radius: 12 * page.u
                color: "#2b2163"
                clip: true
                CrossfadeImage {
                    anchors.fill: parent
                    source: app.artUrl
                    sourceSize: Qt.size(page.width * 0.1, page.width * 0.1)
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6 * page.u
                QQC2.Label {
                    Layout.fillWidth: true
                    text: app.title
                    color: "#ffffff"
                    font.pixelSize: 48 * page.u
                    font.weight: Font.Bold
                    elide: Text.ElideRight
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    text: [app.artist, app.album].filter(s => s !== "").join(" · ")
                    color: "#ffffff"
                    opacity: 0.8
                    font.pixelSize: 30 * page.u
                    elide: Text.ElideRight
                }
            }
        }

        LyricsView {
            anchors { left: parent.left; right: parent.right; top: lyricsHeader.bottom; bottom: parent.bottom
                      topMargin: 24 * page.u }
            u: page.u
            refWidth: page.width
            lines: app.lyricLines
            position: page.position
        }
    }

    // --- bottom bar ---------------------------------------------------------------
    ColumnLayout {
        id: bar
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: page.margin }
        spacing: 28 * page.u

        TrackProgress {
            Layout.fillWidth: true
            u: page.u
            visible: page.hasMedia
            position: page.position
            duration: app.duration
        }

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: playButton.height

            RowLayout {
                anchors.centerIn: parent
                spacing: 40 * page.u

                FocusButton {
                    id: shuffleButton
                    u: page.u
                    iconName: "media-playlist-shuffle"
                    text: app.shuffle ? "Shuffle on" : "Shuffle off"
                    active: app.shuffle
                    KeyNavigation.right: prevButton
                    onClicked: app.toggleShuffle()
                }
                FocusButton {
                    id: prevButton
                    u: page.u
                    iconName: "media-skip-backward"
                    text: "Previous"
                    KeyNavigation.left: shuffleButton
                    KeyNavigation.right: playButton
                    onClicked: app.previous()
                }
                FocusButton {
                    id: playButton
                    u: page.u
                    primary: true
                    iconName: app.isPlaying ? "media-playback-pause" : "media-playback-start"
                    text: app.isPlaying ? "Pause" : "Play"
                    KeyNavigation.left: prevButton
                    KeyNavigation.right: nextButton
                    onClicked: app.playPause()
                }
                FocusButton {
                    id: nextButton
                    u: page.u
                    iconName: "media-skip-forward"
                    text: "Next"
                    KeyNavigation.left: playButton
                    KeyNavigation.right: repeatButton
                    onClicked: app.next()
                }
                FocusButton {
                    id: repeatButton
                    u: page.u
                    iconName: app.repeatMode === "one" ? "media-playlist-repeat-song" : "media-playlist-repeat"
                    text: app.repeatMode === "one" ? "Repeat one" : (app.repeatMode === "all" ? "Repeat all" : "Repeat off")
                    active: app.repeatMode !== "off"
                    KeyNavigation.left: nextButton
                    KeyNavigation.right: volumeButton.visible ? volumeButton : searchButton
                    onClicked: app.cycleRepeat()
                }
                FocusButton {
                    id: volumeButton
                    u: page.u
                    visible: app.hasVolume
                    iconName: app.volume === 0 ? "audio-volume-muted"
                              : app.volume < 34 ? "audio-volume-low"
                              : app.volume < 67 ? "audio-volume-medium" : "audio-volume-high"
                    text: "Volume " + app.volume
                    KeyNavigation.left: repeatButton
                    KeyNavigation.right: searchButton
                    onClicked: { page.placeVolumePopup(); volumePopup.open(true) }
                }
            }

            Row {
                anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                spacing: 20 * page.u
                NavButton {
                    id: searchButton
                    iconName: "edit-find"
                    iconScale: 0.8
                    text: "Search"
                    KeyNavigation.left: volumeButton.visible ? volumeButton : repeatButton
                    KeyNavigation.right: queueButton
                    onClicked: { page.returnFocus = searchButton; page.openPage("search") }
                }
                NavButton {
                    id: queueButton
                    iconName: "view-media-playlist"
                    text: "Queue"
                    KeyNavigation.left: searchButton
                    KeyNavigation.right: speakersButton
                    onClicked: { page.returnFocus = queueButton; page.openPage("queue") }
                }
                NavButton {
                    id: speakersButton
                    iconName: "speaker"
                    text: "Speakers"
                    KeyNavigation.left: queueButton
                    KeyNavigation.right: settingsButton
                    onClicked: { page.returnFocus = speakersButton; page.openPage("speakers") }
                }
                NavButton {
                    id: settingsButton
                    iconName: "configure"
                    text: "Settings"
                    KeyNavigation.left: speakersButton
                    onClicked: { page.returnFocus = settingsButton; page.openSetup() }
                }
            }
        }
    }

    component NavButton: FocusButton { u: page.u; size: 76 * page.u }

    // If the volume button disappears while focused, keep focus on the bar.
    Connections {
        target: volumeButton
        function onVisibleChanged() {
            if (!volumeButton.visible) {
                volumePopup.close()
                if (volumeButton.activeFocus) repeatButton.forceActiveFocus()
            }
        }
    }

    VolumePopup {
        id: volumePopup
        u: page.u
        z: 10
        opener: volumeButton
    }
}
