import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import "nav.js" as Nav

// The bar across the top of every screen: the name (and a warning when something is
// broken: OK opens the logs), the tabs in the middle of the screen, then the speaker in use,
// Guest and Settings. Left/Right move along it (no wrap-around), OK opens, Down goes back
// to the screen (leaveDown). With guest mode on, the QR card takes the Guest button's
// place in the corner and opens the guest list.
FocusScope {
    id: bar
    property real u: 1
    property string screen: "now"
    property var tabs: Nav.ALL_TABS
    property string speakerName: ""
    property bool guestMode: false
    property var qrRows: []
    property string qrCaption: ""
    property string guestUrl: ""
    property string problem: ""          // something broke: the warning button shows
    property bool dimmed: false          // the visualizer fades the bar out while nobody presses a key
    signal go(string screen)
    signal toggleGuest()
    signal leaveDown()

    implicitHeight: 104 * u
    // room the QR card takes below the bar: screens keep their top-right corner clear of it
    readonly property real qrWidth: guestMode ? qrCard.width + 2 * 48 * u : 0
    readonly property real qrBottom: guestMode ? qrCard.y + qrCard.height : 0

    function order() {
        var list = []
        if (problemChip.visible) list.push(problemChip)
        for (var i = 0; i < tabRepeater.count; i++) list.push(tabRepeater.itemAt(i))
        list.push(speakerChip)
        if (guestChip.visible) list.push(guestChip)
        list.push(settingsChip)
        if (qrCard.visible) list.push(qrCard)
        return list
    }
    function focusCurrent() {
        for (var i = 0; i < tabRepeater.count; i++)
            if (tabRepeater.itemAt(i).name === screen) { tabRepeater.itemAt(i).forceActiveFocus(); return }
        var other = { speakers: speakerChip, settings: settingsChip, guests: guestMode ? qrCard : guestChip,
                      logs: problemChip }[screen]
        if (other && other.visible) other.forceActiveFocus()
        else if (tabRepeater.count > 0) tabRepeater.itemAt(0).forceActiveFocus()
    }
    function move(delta) {
        var list = order()
        for (var i = 0; i < list.length; i++) {
            if (list[i].activeFocus) {
                var next = list[Math.max(0, Math.min(list.length - 1, i + delta))]
                next.forceActiveFocus()
                return
            }
        }
    }
    Keys.onLeftPressed: move(-1)
    Keys.onRightPressed: move(1)
    Keys.onDownPressed: leaveDown()
    Keys.onUpPressed: {}    // nothing above the bar

    Rectangle {  // the bar fades into the screen below it
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: "#eb07070b" }
            GradientStop { position: 1; color: "#0007070b" }
        }
    }

    RowLayout {
        id: barRow
        anchors { fill: parent; leftMargin: 48 * bar.u; rightMargin: 48 * bar.u + (bar.guestMode ? qrCard.width + 24 * bar.u : 0) }
        spacing: 24 * bar.u

        Row {  // the name
            spacing: 14 * bar.u
            GradientFill {
                anchors.verticalCenter: parent.verticalCenter
                width: 34 * bar.u; height: width; radius: 9 * bar.u
            }
            Row {
                anchors.verticalCenter: parent.verticalCenter
                Text {
                    textFormat: Text.PlainText
                    text: "Couch"
                    color: Theme.text
                    font.pixelSize: Theme.label * bar.u
                    font.weight: Font.ExtraBold
                }
                Text {
                    textFormat: Text.PlainText
                    text: "side"
                    color: Theme.a1
                    font.pixelSize: Theme.label * bar.u
                    font.weight: Font.ExtraBold
                }
            }
        }

        Chip {   // something broke: OK opens the logs
            id: problemChip
            objectName: "problemChip"
            u: bar.u
            warn: true
            visible: bar.problem !== ""
            iconName: "warning"
            text: "Something's wrong"
            Accessible.name: "Something's wrong: " + bar.problem + ". Show the logs"
            onClicked: bar.go("logs")
        }
        Item { id: nameEnd; Layout.fillWidth: false; Layout.preferredWidth: 0; Layout.fillHeight: true }
        Item { Layout.fillWidth: true; Layout.fillHeight: true }

        Row {
            id: rightRow
            objectName: "rightRow"
            spacing: 12 * bar.u
            Chip {
                id: speakerChip
                objectName: "speakerChip"
                u: bar.u
                dot: true
                active: bar.screen === "speakers"
                maxTextWidth: 260 * bar.u
                text: bar.speakerName !== "" ? bar.speakerName : "Speakers"
                Accessible.name: "Playing on " + text
                onClicked: bar.go("speakers")
            }
            Chip {
                id: guestChip
                objectName: "guestChip"
                u: bar.u
                visible: !bar.guestMode
                iconName: "qr"
                text: "Guest"
                onClicked: bar.toggleGuest()
            }
            Chip {
                id: settingsChip
                objectName: "settingsChip"
                u: bar.u
                iconName: "settings"
                active: bar.screen === "settings"
                Accessible.name: "Settings"
                onClicked: bar.go("settings")
            }
        }
    }

    Row {
        id: tabRow
        objectName: "tabRow"
        // the middle of the screen, unless a long speaker name (or the guest QR) needs that
        // room: then just left of the speaker button, never over the name
        anchors.verticalCenter: parent.verticalCenter
        x: Math.max(barRow.x + nameEnd.x + nameEnd.width + 24 * bar.u,
                    Math.min((bar.width - width) / 2, barRow.x + rightRow.x - 24 * bar.u - width))
        spacing: 4 * bar.u
        Repeater {
            id: tabRepeater
            model: bar.tabs
            delegate: QQC2.AbstractButton {
                id: tab
                required property string modelData
                readonly property string name: modelData
                readonly property bool current: bar.screen === name
                objectName: "tab-" + name
                text: Nav.label(name)
                focusPolicy: Qt.StrongFocus
                leftPadding: 18 * bar.u
                rightPadding: 18 * bar.u
                topPadding: 14 * bar.u
                bottomPadding: 18 * bar.u
                Accessible.name: text
                onClicked: bar.go(name)
                Keys.onReturnPressed: clicked()
                Keys.onEnterPressed: clicked()
                Keys.onPressed: (event) => {
                    if (event.key === Qt.Key_Select) { clicked(); event.accepted = true }
                }
                background: Item {
                    Rectangle {
                        anchors.fill: parent
                        radius: 14 * bar.u
                        color: tab.activeFocus ? Theme.surfaceHigh : "transparent"
                    }
                    FocusRing { anchors.fill: parent; u: bar.u; radius: 14 * bar.u; shown: tab.activeFocus }
                    GradientFill {  // the current tab's underline
                        visible: tab.current
                        anchors { left: parent.left; right: parent.right; bottom: parent.bottom
                                  leftMargin: 18 * bar.u; rightMargin: 18 * bar.u; bottomMargin: 6 * bar.u }
                        height: 4 * bar.u
                        radius: height / 2
                    }
                }
                contentItem: Text {
                    textFormat: Text.PlainText
                    text: tab.text
                    color: tab.current || tab.activeFocus ? Theme.text : Theme.textFaint
                    font.pixelSize: Theme.tab * bar.u
                    font.weight: Font.Bold
                }
            }
        }
    }

    QrCard {
        id: qrCard
        objectName: "qrCard"
        visible: bar.guestMode
        u: bar.u
        anchors { top: parent.top; right: parent.right; topMargin: 20 * bar.u; rightMargin: 48 * bar.u }
        rows: bar.qrRows
        caption: bar.qrCaption
        url: bar.guestUrl
        onClicked: bar.go("guests")
    }
}
