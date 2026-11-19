pragma ComponentBehavior: Bound
import QtQuick

// The guest QR on a white card: the code, the caption, the address. Shown top-right on
// every screen while guest mode is on. Focusable: OK emits clicked() (opens Guests).
FocusScope {
    id: card
    property real u: 1
    property var rows: []
    property string caption: ""
    property string url: ""
    signal clicked()

    implicitWidth: 212 * u
    implicitHeight: column.implicitHeight + 34 * u
    activeFocusOnTab: true

    Keys.onReturnPressed: (event) => { if (!event.isAutoRepeat) clicked() }
    Keys.onEnterPressed: (event) => { if (!event.isAutoRepeat) clicked() }
    Keys.onPressed: (event) => { if (event.key === Qt.Key_Select) { if (!event.isAutoRepeat) clicked(); event.accepted = true } }

    Rectangle { anchors.fill: parent; radius: 20 * card.u; color: "#ffffff" }
    FocusRing { anchors.fill: parent; u: card.u; radius: 20 * card.u; shown: card.activeFocus }

    Column {
        id: column
        anchors { top: parent.top; topMargin: 18 * card.u; horizontalCenter: parent.horizontalCenter }
        width: parent.width - 28 * card.u
        spacing: 10 * card.u
        QrCode {
            anchors.horizontalCenter: parent.horizontalCenter
            rows: card.rows
            size: 184 * card.u
            radius: 0
        }
        Text {
            textFormat: Text.PlainText
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: card.caption
            color: "#14141a"
            font.pixelSize: Theme.small * card.u
            font.weight: Font.ExtraBold
            lineHeight: 1.05
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
        Text {
            textFormat: Text.PlainText
            visible: text !== ""
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            // the address without the scheme and the token: enough to recognise, short enough to fit
            text: card.url.replace(/^https?:\/\//, "").replace(/[\/?#].*$/, "")
            color: "#0a8f80"
            font.pixelSize: 20 * card.u
            font.weight: Font.Bold
            elide: Text.ElideMiddle
        }
    }
    MouseArea { anchors.fill: parent; onClicked: { card.forceActiveFocus(); card.clicked() } }
}
