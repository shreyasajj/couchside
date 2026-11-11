import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: "Couchside"
    visibility: Window.FullScreen
    color: "#0d0b1a"
    // 1.0 at 1080p; every size in the UI is multiplied by this.
    readonly property real u: Math.max(0.5, height / 1080)

    // `flatpak run io.github.shreyasajj.Couchside --debug-focus` logs every focus change.
    readonly property bool debugFocus: Qt.application.arguments.indexOf("--debug-focus") >= 0
    onActiveFocusItemChanged: if (debugFocus) console.log("focus ->", activeFocusItem,
                                                          activeFocusItem ? activeFocusItem.objectName : "")

    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None
    pageStack.columnView.columnResizeMode: Kirigami.ColumnView.SingleColumn
    pageStack.initialPage: nowPlayingComponent

    Component {
        id: nowPlayingComponent
        NowPlayingPage {
            u: root.u
            onOpenSetup: root.showSetup()
            onOpenPage: (name) => root.openPage(name)
        }
    }
    Component {
        id: setupComponent
        SetupPage { objectName: "setup"; u: root.u; onDone: root.goBack() }
    }
    Component { id: libraryComponent; LibraryPage { u: root.u; sheet: actionSheet } }
    Component { id: queueComponent; QueuePage { u: root.u; sheet: actionSheet } }
    Component {
        id: speakersComponent
        SpeakersPage { u: root.u; sheet: actionSheet; groupEditor: groupEditorOverlay }
    }

    function showSetup() {
        if (!pageStack.currentItem || pageStack.currentItem.objectName !== "setup") pageStack.push(setupComponent)
    }
    function openPage(name) {
        var comp = { search: libraryComponent, queue: queueComponent, speakers: speakersComponent }[name]
        if (comp && pageStack.depth === 1) pageStack.push(comp)
    }
    function goBack() {
        if (pairing.visible) { pairing.dismissedCode = app.pairingCode; return }
        if (exitDialog.opened) { exitDialog.close(); return }
        if (actionSheet.visible) { actionSheet.close(); return }
        if (groupEditorOverlay.visible) { groupEditorOverlay.close(); return }
        var page = pageStack.currentItem
        if (page && page.handleBack && page.handleBack()) return
        if (pageStack.depth > 1) {
            pageStack.pop()
            pageStack.currentItem.focusDefault()
        } else {
            exitDialog.open()
        }
    }

    // Open Setup when it becomes needed, not on every update: after Back the user
    // stays where they went until the situation changes again.
    property bool setupWasNeeded: false
    Connections {
        target: app
        function onChanged() {
            if (app.needsSetup && !root.setupWasNeeded) root.showSetup()
            root.setupWasNeeded = app.needsSetup
        }
    }
    Component.onCompleted: { setupWasNeeded = app.needsSetup; if (app.needsSetup) showSetup() }

    // Back on any remote; media keys work wherever focus is.
    Shortcut { sequences: ["Back", "Esc"]; onActivated: root.goBack() }
    Shortcut { sequences: ["Media Play", "Media Pause", "Toggle Media Play/Pause"]; onActivated: app.playPause() }
    Shortcut { sequence: "Media Next"; onActivated: app.next() }
    Shortcut { sequence: "Media Previous"; onActivated: app.previous() }
    Shortcut { sequence: "Volume Up"; onActivated: root.volumeStep(5) }
    Shortcut { sequence: "Volume Down"; onActivated: root.volumeStep(-5) }
    function volumeStep(delta) {
        var page = pageStack.currentItem
        if (page && page.adjustVolume) page.adjustVolume(delta)
        else if (delta > 0) app.volumeUp()
        else app.volumeDown()
    }

    function focusCurrentPage() {
        var page = pageStack.currentItem
        if (page && page.focusDefault) page.focusDefault()
    }
    ActionSheet { id: actionSheet; u: root.u; parent: root.overlay; onFocusLost: root.focusCurrentPage() }
    GroupEditor { id: groupEditorOverlay; u: root.u; parent: root.overlay; onFocusLost: root.focusCurrentPage() }
    Toast { u: root.u; parent: root.overlay }

    PairingOverlay {
        id: pairing
        u: root.u
        z: 100
        parent: root.overlay
        // Never cover the Connect page (the token is typed there); Back hides this code.
        property string dismissedCode: ""
        visible: app.pairingCode !== "" && app.pairingCode !== dismissedCode && pageStack.depth < 2
        onVisibleChanged: {
            if (visible) forceActiveFocus()
            else if (pageStack.currentItem && pageStack.currentItem.focusDefault) pageStack.currentItem.focusDefault()
        }
    }

    QQC2.Dialog {
        id: exitDialog
        anchors.centerIn: parent
        modal: true
        padding: 48 * root.u
        onOpened: cancelButton.forceActiveFocus()
        onClosed: if (pageStack.currentItem && pageStack.currentItem.focusDefault) pageStack.currentItem.focusDefault()
        background: Rectangle { color: "#1d1840"; radius: 16 * root.u }
        contentItem: ColumnLayout {
            spacing: 36 * root.u
            QQC2.Label {
                text: "Exit Couchside?"
                color: "#ffffff"
                font.pixelSize: 44 * root.u
                font.weight: Font.Bold
            }
            QQC2.Label {
                text: "Music keeps playing on this TV."
                color: "#ffffff"
                opacity: 0.8
                font.pixelSize: 30 * root.u
            }
            RowLayout {
                spacing: 28 * root.u
                DialogButton {
                    id: cancelButton
                    text: "Cancel"
                    KeyNavigation.right: exitButton
                    onClicked: exitDialog.close()
                }
                DialogButton {
                    id: exitButton
                    text: "Exit"
                    KeyNavigation.left: cancelButton
                    onClicked: Qt.quit()
                }
            }
        }
    }

    component DialogButton: QQC2.Button {
        id: btn
        font.pixelSize: 32 * root.u
        padding: 22 * root.u
        Keys.onReturnPressed: clicked()
        Keys.onEnterPressed: clicked()
        background: Rectangle {
            radius: 12 * root.u
            color: btn.activeFocus ? "#ffffff" : "#33ffffff"
            border.width: btn.activeFocus ? 6 * root.u : 0
            border.color: "#4fc3f7"
        }
        contentItem: QQC2.Label {
            text: btn.text
            font: btn.font
            color: btn.activeFocus ? "#000000" : "#ffffff"
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
