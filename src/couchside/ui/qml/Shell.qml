import QtQuick
import QtQuick.Layouts
import "nav.js" as Nav

// Everything on screen: the top bar, the screen under it, and the overlays. Tabs (Now
// Playing, Search, Queue, Lyrics, Visualizer) and the screens without a tab (Speakers,
// Guests, Settings, a content page opened from outside) swap in one place; nothing stacks.
// Up from a screen's top row reaches the bar; Down returns to where focus was.
// Kirigami-free on purpose, so the whole UI loads in tests.
FocusScope {
    id: shell
    // 1.0 at 1080p; every size in the UI is multiplied by this.
    readonly property real u: Math.max(0.5, height / 1080)
    property string screen: "now"
    property string lastTab: "now"      // the tab a screen without one was opened from
    property string backTo: ""          // the tab-less screen another one was opened from (Settings → Guests)
    property Item lastFocus: null       // where focus was before it went up to the bar
    property var contentData: ({})      // the item a content page shows
    property bool bridgeSearch: false   // Search opened from outside: its results are already loading
    signal raiseRequested()             // bring the window to the front (asked from outside)

    readonly property bool appActive: Qt.application.state === Qt.ApplicationActive
    // The Visualizer tab always shows (it listens only while open); Lyrics follows its setting.
    readonly property var tabs: Nav.tabs(app.lyricsEnabled, true)
    onTabsChanged: if (Nav.validScreen(screen, app.lyricsEnabled, true) !== screen) go("now")
    readonly property string speakerName: {
        var rows = app.speakerRows
        for (var i = 0; i < rows.length; i++) if (rows[i].controlled) return rows[i].name
        return ""
    }

    // The colours chosen in Settings → Look.
    Binding { target: Theme; property: "a1"; value: app.accent1 }
    Binding { target: Theme; property: "a2"; value: app.accent2 }

    // --- what the controller needs to know about the screen -----------------------------
    Binding { target: app; property: "pulseVisible"; value: shell.screen === "now" && shell.appActive }
    Binding { target: app; property: "vizVisible"; value: shell.screen === "visualizer" && shell.appActive }
    Binding { target: app; property: "queueVisible"; value: shell.screen === "now" || shell.screen === "queue" }

    // --- progress, ticked locally between server updates ---------------------------------
    property real position: 0
    function updatePosition() {
        var p = app.positionBase
        if (app.isPlaying) p += Date.now() / 1000 - app.positionAt
        p = Math.max(0, p)
        if (app.hasDuration) p = Math.min(app.duration, p)
        position = p
    }
    Timer {
        interval: (shell.screen === "lyrics" || shell.screen === "visualizer") ? 250 : 500  // lyrics need a finer tick
        repeat: true
        running: app.isPlaying && shell.appActive
        triggeredOnStart: true
        onTriggered: shell.updatePosition()
    }

    // --- moving between screens ----------------------------------------------------------
    function currentItem() { return screen === "now" ? nowPage : loader.item }
    function overlayOpen() {
        return pairing.visible || adminCode.visible || exitConfirm.visible || actionSheet.visible
               || groupEditorOverlay.visible
    }
    function focusScreen() {
        if (overlayOpen()) return
        var item = currentItem()
        if (item && item.focusDefault) item.focusDefault()
        else content.forceActiveFocus()
    }
    function go(name) {
        name = Nav.validScreen(name, app.lyricsEnabled, true)
        if (name !== screen) {
            if (Nav.isTab(screen)) lastTab = screen
            backTo = (!Nav.isTab(screen) && !Nav.isTab(name)) ? screen : ""
            lastFocus = null
            screen = name   // the Loader swaps the screen at once
        }
        focusScreen()
    }
    function inContent(item) {
        for (var p = item; p; p = p.parent) if (p === content) return true
        return false
    }
    function enterBar() {
        var item = Window.activeFocusItem
        lastFocus = inContent(item) ? item : null
        topBar.focusCurrent()
    }
    function leaveBar() {
        if (lastFocus && lastFocus.visible && inContent(lastFocus)) lastFocus.forceActiveFocus()
        else focusScreen()
    }
    function closeOverlays() {
        exitConfirm.close()
        actionSheet.close()
        groupEditorOverlay.close()
        volumePopup.close()
        app.closeAdminCode()
    }
    function goBack() {
        if (pairing.visible) { pairing.dismissedCode = app.pairingCode; return }
        if (adminCode.visible) { app.closeAdminCode(); return }
        if (exitConfirm.visible) { exitConfirm.close(); return }
        if (actionSheet.visible) { actionSheet.close(); return }
        if (groupEditorOverlay.visible) { groupEditorOverlay.close(); return }
        if (volumePopup.interactive) { volumePopup.close(); return }
        var item = currentItem()
        if (item && item.handleBack && item.handleBack()) return
        if (topBar.activeFocus) { leaveBar(); return }
        if (backTo !== "") { var prev = backTo; go(prev); backTo = ""; return }
        var to = Nav.back(screen, lastTab)
        if (to === "exit") exitConfirm.open()
        else go(to)
    }
    function volumeStep(delta) {
        if (app.hasVolume) volumePopup.flash(delta)
        else if (delta > 0) app.volumeUp()
        else app.volumeDown()
    }

    // Open Settings when it becomes needed, not on every update: after Back the user
    // stays where they went until the situation changes again.
    property bool setupWasNeeded: false
    Connections {
        target: app
        function onChanged() {
            shell.updatePosition()
            if (app.needsSetup && !shell.setupWasNeeded) shell.go("settings")
            shell.setupWasNeeded = app.needsSetup
        }
    }
    Component.onCompleted: {
        setupWasNeeded = app.needsSetup
        if (app.needsSetup) go("settings")
        else focusScreen()
    }

    // --- opened from outside (Bigscreen Bridge): show a screen, never start playback ------
    Connections {
        target: typeof bridgeControl !== "undefined" ? bridgeControl : null
        function onNavigationRequested(requestId, kind, payloadJson) {
            try {
                const payload = JSON.parse(payloadJson)
                if (kind !== "focus") {
                    shell.closeOverlays()
                    if (kind === "search") {
                        shell.bridgeSearch = true
                        shell.go("search")
                        shell.bridgeSearch = false
                        loader.item.setBridgeQuery(payload.value)
                    } else if (kind === "now_playing") {
                        shell.go("now")
                    } else {
                        shell.contentData = payload.item
                        shell.go("content")
                    }
                }
                shell.raiseRequested()
                Qt.callLater(function() {
                    const expected = kind === "search" ? "search" : kind === "now_playing" ? "now" : "content"
                    bridgeControl.completeNavigation(requestId, kind === "focus" || shell.screen === expected)
                })
            } catch (error) {
                console.warn("Bridge navigation failed:", error)
                bridgeControl.completeNavigation(requestId, false)
            }
        }
    }

    // Back on any remote; media and volume keys work wherever focus is.
    Shortcut { sequences: ["Back", "Esc"]; onActivated: shell.goBack() }
    Shortcut { sequences: ["Media Play", "Media Pause", "Toggle Media Play/Pause"]; onActivated: app.playPause() }
    Shortcut { sequence: "Media Next"; onActivated: app.next() }
    Shortcut { sequence: "Media Previous"; onActivated: app.previous() }
    Shortcut { sequence: "Volume Up"; onActivated: shell.volumeStep(5) }
    Shortcut { sequence: "Volume Down"; onActivated: shell.volumeStep(-5) }

    Rectangle { anchors.fill: parent; color: Theme.bg }

    // --- the screens ---------------------------------------------------------------------
    FocusScope {
        id: content
        objectName: "content"
        anchors.fill: parent
        // whatever a screen doesn't use Up for (its top row) goes to the bar
        Keys.onUpPressed: shell.enterBar()

        NowPlayingPage {   // kept alive: it is the screen you come back to
            id: nowPage
            objectName: "now"
            anchors.fill: parent
            visible: shell.screen === "now"
            u: shell.u
            position: shell.position
            topInset: topBar.height
            qrBottom: topBar.qrBottom
            onOpenPage: (name) => shell.go(name)
            onOpenVolume: (opener) => { volumePopup.opener = opener; volumePopup.open(true) }
            onTyped: (text) => {
                shell.go("search")
                if (loader.item && loader.item.typeInto) loader.item.typeInto(text)
            }
        }
        Loader {
            id: loader
            anchors.fill: parent
            active: shell.screen !== "now"
            sourceComponent: ({ search: searchScreen, queue: queueScreen, lyrics: lyricsScreen,
                                visualizer: visualizerScreen, speakers: speakersScreen,
                                guests: guestsScreen, settings: settingsScreen,
                                content: contentScreen })[shell.screen] || null
        }
    }
    Component { id: searchScreen; LibraryPage { u: shell.u; sheet: actionSheet; topInset: topBar.height; qrWidth: topBar.qrWidth; qrBottom: topBar.qrBottom; bridgeManaged: shell.bridgeSearch } }
    Component { id: queueScreen; QueuePage { u: shell.u; sheet: actionSheet; topInset: topBar.height; qrWidth: topBar.qrWidth; qrBottom: topBar.qrBottom } }
    Component { id: lyricsScreen; LyricsPage { u: shell.u; position: shell.position; topInset: topBar.height; qrWidth: topBar.qrWidth } }
    Component {
        id: visualizerScreen
        VisualizerPage { u: shell.u; sheet: actionSheet; position: shell.position; topInset: topBar.height
                         active: shell.appActive }
    }
    Component {
        id: speakersScreen
        SpeakersPage { u: shell.u; sheet: actionSheet; groupEditor: groupEditorOverlay; topInset: topBar.height; qrWidth: topBar.qrWidth; qrBottom: topBar.qrBottom }
    }
    Component { id: guestsScreen; GuestsPage { u: shell.u; sheet: actionSheet; topInset: topBar.height; qrWidth: topBar.qrWidth; qrBottom: topBar.qrBottom } }
    Component {
        id: settingsScreen
        SetupPage { u: shell.u; sheet: actionSheet; topInset: topBar.height; qrWidth: topBar.qrWidth; qrBottom: topBar.qrBottom
                    onDone: shell.goBack(); onOpenGuests: shell.go("guests") }
    }
    Component { id: contentScreen; ContentPage { u: shell.u; sheet: actionSheet; item: shell.contentData; topInset: topBar.height } }

    // --- the bar -------------------------------------------------------------------------
    TopBar {
        id: topBar
        objectName: "topBar"
        anchors { left: parent.left; right: parent.right; top: parent.top }
        z: 60
        u: shell.u
        screen: shell.screen
        tabs: shell.tabs
        speakerName: shell.speakerName
        guestMode: app.guestMode
        qrRows: app.qrRows
        qrCaption: app.qrCaption
        guestUrl: app.guestUrl
        // the visualizer hides it while nobody presses a key; it comes back with focus
        readonly property bool hiddenByScreen: !activeFocus && loader.item !== null && loader.item.chromeHidden === true
        opacity: hiddenByScreen ? 0 : 1
        enabled: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.fadeMs } }
        onGo: (name) => shell.go(name)
        onToggleGuest: app.toggleGuestMode()
        onLeaveDown: shell.leaveBar()
    }

    // --- overlays ------------------------------------------------------------------------
    VolumePopup {
        id: volumePopup
        u: shell.u
        z: 150
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 250 * shell.u }
    }
    ActionSheet { id: actionSheet; u: shell.u; onFocusLost: shell.focusScreen() }
    GroupEditor { id: groupEditorOverlay; u: shell.u; onFocusLost: shell.focusScreen() }
    Toast { u: shell.u }

    PairingOverlay {
        id: pairing
        u: shell.u
        z: 260
        // Never cover Settings (the token is typed there); Back hides this code.
        property string dismissedCode: ""
        visible: app.pairingCode !== "" && app.pairingCode !== dismissedCode && shell.screen !== "settings"
        onVisibleChanged: if (visible) forceActiveFocus(); else shell.focusScreen()
    }
    AdminCodeOverlay {
        id: adminCode
        u: shell.u
        z: 250
        visible: app.adminCode !== ""
        onVisibleChanged: if (visible) forceActiveFocus(); else shell.focusScreen()
    }

    // Back on Now Playing: leave only after a yes.
    Rectangle {
        id: exitConfirm
        objectName: "exitConfirm"
        anchors.fill: parent
        z: 240
        visible: false
        color: Theme.scrim
        function open() { visible = true; cancelButton.forceActiveFocus() }
        function close() { if (!visible) return; visible = false; shell.focusScreen() }
        // holds focus and swallows keys, so nothing behind it reacts; Back is a Shortcut
        Keys.onPressed: (event) => { event.accepted = true }
        MouseArea { anchors.fill: parent }
        Rectangle {
            anchors.centerIn: parent
            width: box.implicitWidth + 112 * shell.u
            height: box.implicitHeight + 104 * shell.u
            radius: 24 * shell.u
            color: Theme.panel
            border.width: Math.max(1, shell.u)
            border.color: Theme.border
            ColumnLayout {
                id: box
                anchors.centerIn: parent
                spacing: 16 * shell.u
                Text {
                    textFormat: Text.PlainText
                    text: "Exit Couchside?"
                    color: Theme.text
                    font.pixelSize: Theme.title * shell.u
                    font.weight: Font.ExtraBold
                }
                Text {
                    textFormat: Text.PlainText
                    text: "Music keeps playing on this TV."
                    color: Theme.textDim
                    font.pixelSize: Theme.body * shell.u
                }
                RowLayout {
                    Layout.topMargin: 24 * shell.u
                    spacing: 24 * shell.u
                    PillButton {
                        id: cancelButton
                        objectName: "exitCancel"
                        u: shell.u
                        text: "Cancel"
                        KeyNavigation.right: exitButton
                        onClicked: exitConfirm.close()
                    }
                    PillButton {
                        id: exitButton
                        objectName: "exitYes"
                        u: shell.u
                        text: "Exit"
                        KeyNavigation.left: cancelButton
                        onClicked: Qt.quit()
                    }
                }
            }
        }
    }
}
