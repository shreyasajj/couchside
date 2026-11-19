pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts

// A music item opened from outside (Bigscreen Bridge). Playback is an explicit action here.
FocusScope {
    id: page
    objectName: "bridgeContent"
    property real u: 1
    property var item: ({})
    property var sheet: null
    property real topInset: 104 * u
    function focusDefault() { actions.forceActiveFocus() }
    Component.onCompleted: focusDefault()

    RowLayout {
        anchors { fill: parent; topMargin: page.topInset + 56 * page.u; leftMargin: 150 * page.u
                  rightMargin: 150 * page.u; bottomMargin: 72 * page.u }
        spacing: 64 * page.u
        Cover {
            Layout.preferredWidth: 480 * page.u
            Layout.preferredHeight: 480 * page.u
            Layout.alignment: Qt.AlignTop
            radius: 28 * page.u
            source: page.item.imageUrl || ""
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            spacing: 16 * page.u
            Text {
                textFormat: Text.PlainText
                text: (page.item.kind || "").toUpperCase()
                color: Theme.a1
                font.pixelSize: Theme.label * page.u
                font.weight: Font.Bold
                font.letterSpacing: 2 * page.u
            }
            Text {
                textFormat: Text.PlainText
                Layout.fillWidth: true
                text: page.item.title || ""
                wrapMode: Text.Wrap
                maximumLineCount: 3
                elide: Text.ElideRight
                color: Theme.text
                font.pixelSize: Theme.display * page.u
                font.weight: Font.ExtraBold
                lineHeight: 1.02
            }
            Text {
                textFormat: Text.PlainText
                Layout.fillWidth: true
                text: page.item.subtitle || ""
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
                color: Theme.textDim
                font.pixelSize: Theme.subtitle * page.u
                font.weight: Font.Medium
            }
            PillButton {
                id: actions
                Layout.topMargin: 28 * page.u
                u: page.u
                strong: true
                text: "Play or add to queue"
                onClicked: page.sheet.open(page.item.title, [
                    { id: "now", label: "Play now" },
                    { id: "next", label: "Play next" },
                    { id: "add", label: "Add to queue" }
                ], actions, mode => app.playUri(page.item.uri, mode))
            }
        }
    }
}
