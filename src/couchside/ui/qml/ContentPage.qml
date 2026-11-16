import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// A music item opened by the bridge. Playback is an explicit action in Couchside.
Kirigami.Page {
    id: page
    objectName: "bridgeContent"
    property real u: 1
    property var item: ({})
    property var sheet: null
    padding: 0
    globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None
    background: Rectangle { color: "#0d0b1a" }
    function focusDefault() { actions.forceActiveFocus() }
    Component.onCompleted: focusDefault()

    RowLayout {
        anchors { fill: parent; margins: 72 * page.u }
        spacing: 56 * page.u
        Image {
            source: page.item.imageUrl || ""
            Layout.preferredWidth: 420 * page.u
            Layout.preferredHeight: 420 * page.u
            fillMode: Image.PreserveAspectFit
            asynchronous: true
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 28 * page.u
            QQC2.Label {
                text: page.item.kind || ""
                textFormat: Text.PlainText
                color: "#cccccc"
                font.pixelSize: 28 * page.u
            }
            QQC2.Label {
                text: page.item.title || ""
                textFormat: Text.PlainText
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                color: "#ffffff"
                font.pixelSize: 48 * page.u
                font.bold: true
            }
            QQC2.Label {
                text: page.item.subtitle || ""
                textFormat: Text.PlainText
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                color: "#cccccc"
                font.pixelSize: 30 * page.u
            }
            QQC2.Button {
                id: actions
                text: "Play or add to queue"
                font.pixelSize: 32 * page.u
                padding: 24 * page.u
                Keys.onReturnPressed: clicked()
                Keys.onEnterPressed: clicked()
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Select) { clicked(); event.accepted = true }
                }
                onClicked: page.sheet.open(page.item.title, [
                    { id: "now", label: "Play now" },
                    { id: "next", label: "Play next" },
                    { id: "add", label: "Add to queue" }
                ], actions, mode => app.playUri(page.item.uri, mode))
                background: Rectangle {
                    radius: 12 * page.u
                    color: actions.activeFocus ? "#ffffff" : "#334455"
                    border.width: actions.activeFocus ? 5 * page.u : 0
                    border.color: "#ffffff"
                }
                contentItem: QQC2.Label {
                    text: actions.text
                    font: actions.font
                    color: actions.activeFocus ? "#000000" : "#ffffff"
                }
            }
            Item { Layout.fillHeight: true }
        }
    }
}
