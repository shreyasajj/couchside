import QtQuick
import QtQuick.Layouts

// Logs (from the warning button in the top bar, or Settings → This speaker → Logs): what is
// wrong right now, a button to restart this TV's speaker, and the recent log of either
// the speaker (Sendspin) or Couchside itself. Up/Down scroll the log (newest at the
// bottom, where it opens); it refreshes every few seconds.
FocusScope {
    id: page
    property real u: 1
    property real topInset: 104 * u
    property real qrWidth: 0
    property string which: "sendspin"      // sendspin | app

    function focusDefault() { restartButton.forceActiveFocus() }
    Component.onCompleted: { app.loadLogs(); focusDefault() }

    readonly property string text: which === "sendspin" ? app.sendspinLog : app.appLog
    // keep the newest lines in view unless the remote scrolled up to read
    property bool following: true
    onTextChanged: if (following) Qt.callLater(function() { flick.contentY = Math.max(0, flick.contentHeight - flick.height) })
    onWhichChanged: { following = true; Qt.callLater(function() { flick.contentY = Math.max(0, flick.contentHeight - flick.height) }) }

    Timer { interval: 5000; repeat: true; running: page.visible; onTriggered: app.loadLogs() }

    ColumnLayout {
        anchors { fill: parent; topMargin: page.topInset + 24 * page.u; bottomMargin: 48 * page.u
                  leftMargin: Theme.margin * page.u; rightMargin: Math.max(Theme.margin * page.u, page.qrWidth) }
        spacing: 22 * page.u

        Text {
            textFormat: Text.PlainText
            text: app.problem !== "" ? "Something's wrong" : "Logs"
            color: Theme.text
            font.pixelSize: Theme.title * page.u
            font.weight: Font.ExtraBold
        }
        Repeater {   // everything wrong right now
            model: app.problems
            delegate: Row {
                required property string modelData
                spacing: 14 * page.u
                Icon {
                    anchors.verticalCenter: parent.verticalCenter
                    name: "warning"
                    size: 32 * page.u
                    color: Theme.warn
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    textFormat: Text.PlainText
                    text: modelData
                    color: Theme.warn
                    font.pixelSize: Theme.body * page.u
                    font.weight: Font.Bold
                }
            }
        }
        Text {
            visible: app.problems.length === 0
            textFormat: Text.PlainText
            text: "Nothing is wrong right now."
            color: Theme.textDim
            font.pixelSize: Theme.body * page.u
        }

        Row {
            spacing: 16 * page.u
            PillButton {
                id: restartButton
                objectName: "restartSpeaker"
                u: page.u
                strong: true
                text: "Restart this TV's speaker"
                KeyNavigation.right: sendspinButton
                KeyNavigation.down: logPanel
                onClicked: app.restartSpeaker()
            }
            PillButton {
                id: sendspinButton
                objectName: "showSendspinLog"
                u: page.u
                text: "Speaker log"
                opacity: page.which === "sendspin" ? 1 : 0.7
                KeyNavigation.left: restartButton
                KeyNavigation.right: appButton
                KeyNavigation.down: logPanel
                onClicked: page.which = "sendspin"
            }
            PillButton {
                id: appButton
                objectName: "showAppLog"
                u: page.u
                text: "Couchside log"
                opacity: page.which === "app" ? 1 : 0.7
                KeyNavigation.left: sendspinButton
                KeyNavigation.down: logPanel
                onClicked: page.which = "app"
            }
        }

        FocusScope {   // the log: Up/Down scroll it; Up at the top goes back to the buttons
            id: logPanel
            objectName: "logPanel"
            Layout.fillWidth: true
            Layout.fillHeight: true
            activeFocusOnTab: true
            readonly property real step: Theme.small * page.u * 1.4 * 4   // four lines
            function scroll(delta) {
                var max = Math.max(0, flick.contentHeight - flick.height)
                flick.contentY = Math.max(0, Math.min(max, flick.contentY + delta))
                page.following = flick.contentY >= max - 2
            }
            Keys.onDownPressed: scroll(step)
            Keys.onUpPressed: {
                if (flick.contentY <= 0) restartButton.forceActiveFocus()
                else scroll(-step)
            }

            Rectangle {
                anchors.fill: parent
                radius: 20 * page.u
                color: Theme.panel
                border.width: Math.max(1, page.u)
                border.color: Theme.border
            }
            FocusRing { anchors.fill: parent; u: page.u; radius: 20 * page.u; shown: logPanel.activeFocus }
            Flickable {
                id: flick
                anchors { fill: parent; margins: 24 * page.u }
                clip: true
                contentWidth: width
                contentHeight: logText.paintedHeight
                boundsBehavior: Flickable.StopAtBounds
                Text {
                    id: logText
                    width: flick.width
                    textFormat: Text.PlainText
                    text: page.text
                    color: Theme.textDim
                    wrapMode: Text.WrapAnywhere
                    font.family: "monospace"
                    font.pixelSize: Theme.small * page.u
                    lineHeight: 1.15
                }
            }
            Text {
                anchors { right: parent.right; bottom: parent.bottom; margins: 20 * page.u }
                visible: logPanel.activeFocus
                textFormat: Text.PlainText
                text: "Up/Down scroll"
                color: Theme.textFaint
                font.pixelSize: Theme.small * page.u
            }
        }
    }
}
