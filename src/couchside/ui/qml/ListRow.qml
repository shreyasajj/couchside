import QtQuick
import QtQuick.Layouts

// One focusable list row: art or icon, title, subtitle, badges, trailing text.
// OK/Enter/Select emits activated(). The focused row is white with dark text.
FocusScope {
    id: row
    property real u: 1
    property string imageUrl: ""
    property string iconName: "music"
    property string title: ""
    property string subtitle: ""
    property var badges: []
    property string trailing: ""
    property bool dimmed: false
    property bool marked: false  // e.g. the song playing now
    signal activated()
    readonly property color ink: activeFocus ? Theme.focusText : Theme.text

    implicitHeight: 132 * u
    activeFocusOnTab: true

    Keys.onReturnPressed: (event) => { if (!event.isAutoRepeat) activated() }
    Keys.onEnterPressed: (event) => { if (!event.isAutoRepeat) activated() }
    Keys.onPressed: (event) => { if (event.key === Qt.Key_Select) { if (!event.isAutoRepeat) activated(); event.accepted = true } }

    Rectangle {
        anchors.fill: parent
        radius: 20 * row.u
        color: row.activeFocus ? Theme.focus : (row.marked ? Theme.surface : "transparent")
    }

    RowLayout {
        anchors { fill: parent; leftMargin: 20 * row.u; rightMargin: 32 * row.u }
        spacing: 28 * row.u
        opacity: row.dimmed ? 0.5 : 1

        Rectangle {
            Layout.preferredWidth: 96 * row.u
            Layout.preferredHeight: 96 * row.u
            radius: 12 * row.u
            color: row.activeFocus ? "#1f000000" : Theme.surfaceHigh
            clip: true
            Icon {
                anchors.centerIn: parent
                size: parent.width * 0.5
                name: row.iconName
                color: row.ink
                opacity: 0.7
                visible: art.status !== Image.Ready
            }
            Image {
                id: art
                anchors.fill: parent
                source: row.imageUrl
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize: Qt.size(192, 192)
                visible: status === Image.Ready
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4 * row.u
            RowLayout {
                Layout.fillWidth: true
                spacing: 16 * row.u
                Text {
                    textFormat: Text.PlainText
                    Layout.fillWidth: true
                    text: row.title
                    color: row.ink
                    font.pixelSize: Theme.body * row.u
                    font.weight: row.marked ? Font.Bold : Font.Normal
                    elide: Text.ElideRight
                }
                Repeater {
                    model: row.badges
                    delegate: Rectangle {
                        required property string modelData
                        radius: height / 2
                        color: row.activeFocus ? "#1f000000" : "#334fc3f7"
                        implicitHeight: badge.implicitHeight + 8 * row.u
                        implicitWidth: badge.implicitWidth + 32 * row.u
                        Text {
                            id: badge
                            textFormat: Text.PlainText
                            anchors.centerIn: parent
                            text: parent.modelData
                            color: row.activeFocus ? Theme.focusText : "#bfeaff"
                            font.pixelSize: Theme.label * row.u
                        }
                    }
                }
            }
            Text {
                textFormat: Text.PlainText
                Layout.fillWidth: true
                visible: text !== ""
                text: row.subtitle
                color: row.ink
                opacity: 0.7
                font.pixelSize: Theme.label * row.u
                elide: Text.ElideRight
            }
        }

        Text {
            textFormat: Text.PlainText
            visible: text !== ""
            text: row.trailing
            color: row.ink
            opacity: 0.7
            font.pixelSize: Theme.label * row.u
            font.features: { "tnum": 1 }
        }
    }

    MouseArea { anchors.fill: parent; onClicked: { row.forceActiveFocus(); row.activated() } }
}
