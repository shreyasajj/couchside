import QtQuick
import QtQuick.Layouts

// The "Up Next" card on Now Playing: the next few songs. Focusable as one thing; OK emits
// activated() (the page opens the queue). rows: [{title, subtitle, imageUrl, trailing,
// addedBy}]; who added a song shows under it.
FocusScope {
    id: card
    property real u: 1
    property var rows: []
    property int maxRows: 4
    property int total: rows.length      // how many are waiting in all (the count in the corner)
    readonly property int shown: Math.min(maxRows, rows.length)
    signal activated()

    visible: rows.length > 0
    implicitWidth: 432 * u
    implicitHeight: column.implicitHeight + 44 * u
    activeFocusOnTab: true

    Keys.onReturnPressed: (event) => { if (!event.isAutoRepeat) activated() }
    Keys.onEnterPressed: (event) => { if (!event.isAutoRepeat) activated() }
    Keys.onPressed: (event) => { if (event.key === Qt.Key_Select) { if (!event.isAutoRepeat) activated(); event.accepted = true } }

    Rectangle {
        anchors.fill: parent
        radius: 24 * card.u
        color: "#990a0a10"
        border.width: Math.max(1, card.u)
        border.color: Theme.border
    }
    FocusRing { anchors.fill: parent; u: card.u; radius: 24 * card.u; shown: card.activeFocus }

    ColumnLayout {
        id: column
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 22 * card.u }
        spacing: 14 * card.u
        RowLayout {
            Layout.fillWidth: true
            Text {
                textFormat: Text.PlainText
                Layout.fillWidth: true
                text: "Up Next"
                color: Theme.text
                font.pixelSize: Theme.label * card.u
                font.weight: Font.ExtraBold
            }
            Text {
                textFormat: Text.PlainText
                text: card.total === 1 ? "1 song" : card.total + " songs"
                color: Theme.textDim
                font.pixelSize: Theme.small * card.u
                font.weight: Font.DemiBold
            }
        }
        Repeater {
            model: card.rows.slice(0, card.shown)
            delegate: RowLayout {
                id: line
                required property var modelData
                Layout.fillWidth: true
                spacing: 15 * card.u
                Rectangle {
                    Layout.preferredWidth: 64 * card.u
                    Layout.preferredHeight: 64 * card.u
                    radius: 10 * card.u
                    color: Theme.surfaceHigh
                    clip: true
                    Image {
                        anchors.fill: parent
                        source: line.modelData.imageUrl || ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize: Qt.size(128, 128)
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Text {
                        textFormat: Text.PlainText
                        Layout.fillWidth: true
                        text: line.modelData.title || ""
                        color: Theme.text
                        font.pixelSize: Theme.label * card.u
                        font.weight: Font.Bold
                        elide: Text.ElideRight
                    }
                    Text {
                        textFormat: Text.PlainText
                        Layout.fillWidth: true
                        visible: text !== ""
                        text: line.modelData.subtitle || ""
                        color: Theme.textDim
                        font.pixelSize: Theme.small * card.u
                        elide: Text.ElideRight
                    }
                    Text {
                        textFormat: Text.PlainText
                        objectName: "upNextCredit"
                        Layout.fillWidth: true
                        visible: text !== ""
                        text: line.modelData.addedBy ? "Added by " + line.modelData.addedBy : ""
                        color: Theme.a1
                        font.pixelSize: Theme.small * card.u
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                }
                Text {
                    textFormat: Text.PlainText
                    visible: text !== ""
                    text: line.modelData.trailing || ""
                    color: Theme.textFaint
                    font.pixelSize: Theme.small * card.u
                    font.features: { "tnum": 1 }
                }
            }
        }
    }
    MouseArea { anchors.fill: parent; onClicked: { card.forceActiveFocus(); card.activated() } }
}
