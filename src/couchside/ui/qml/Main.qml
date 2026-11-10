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

    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None
    pageStack.columnView.columnResizeMode: Kirigami.ColumnView.SingleColumn
    pageStack.initialPage: homeComponent

    Component {
        id: homeComponent
        HomePage { u: root.u; onOpenSetup: root.showSetup() }
    }
    Component {
        id: setupComponent
        SetupPage { u: root.u; onDone: root.goBack() }
    }

    function showSetup() {
        if (pageStack.depth < 2) pageStack.push(setupComponent)
    }
    function goBack() {
        if (exitDialog.opened) { exitDialog.close(); return }
        if (pageStack.depth > 1) {
            pageStack.pop()
            pageStack.currentItem.focusDefault()
        } else {
            exitDialog.open()
        }
    }

    Connections {
        target: app
        function onChanged() { if (app.needsSetup) root.showSetup() }
    }
    Component.onCompleted: if (app.needsSetup) showSetup()

    // Back on any remote; media keys work wherever focus is.
    Shortcut { sequences: ["Back", "Esc"]; onActivated: root.goBack() }
    Shortcut { sequences: ["Media Play", "Media Pause", "Toggle Media Play/Pause"]; onActivated: app.playPause() }
    Shortcut { sequence: "Media Next"; onActivated: app.next() }
    Shortcut { sequence: "Media Previous"; onActivated: app.previous() }

    PairingOverlay { u: root.u; z: 100; parent: root.overlay }

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
